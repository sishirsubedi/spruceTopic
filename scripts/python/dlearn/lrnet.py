import torch; torch.manual_seed(0)
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
import numpy as np
import pandas as pd
import annoy 
import sys
import time
import logging
logger = logging.getLogger(__name__)

class ApproxNN():
    def __init__(self, data, labels):
        self.dimension = data.shape[1]
        self.data = data.astype('float32')
        self.labels = labels    
   
    def build(self, number_of_trees=50):
        self.index = annoy.AnnoyIndex(self.dimension,'angular')
        for i, vec in enumerate(self.data):
            self.index.add_item(i, vec.tolist())
        self.index.build(number_of_trees)
        
    def query(self, vector, k):
        indices = self.index.get_nns_by_vector(vector.tolist(),k)                                           
        # return [self.labels[i] for i in indices]
        return indices

class LRDataset(Dataset):
	def __init__(self,lmat,rmat,labels,Alr,modelann,nbrsize,hmat,device) :
		self.lmat = lmat
		self.rmat = rmat
		self.labels = labels
		self.lrmat = Alr
		self.modelann = modelann
		self.nbrsize = nbrsize
		self.hmat = hmat 
		self.device = device

	def __len__(self):
		return self.hmat.shape[0]
	
	def __getitem__(self, idx):

		neighbours = self.modelann.query(self.hmat[idx],k=self.nbrsize)

		l_in_mat,r_in_mat = [],[]

		cm_l = self.lmat[idx].unsqueeze(0)
		cm_r = self.rmat[idx].unsqueeze(0)

		for nidx in neighbours[1:]:
			
			cn_l = self.lmat[nidx].unsqueeze(0)
			cn_r = self.rmat[nidx].unsqueeze(0)

			l_in_mat.append(torch.mm(cm_l,self.lrmat).mul(cm_r) + torch.mm(cn_l,self.lrmat).mul(cn_r))
			r_in_mat.append(torch.mm(cm_r,torch.t(self.lrmat)).mul(cm_l) + torch.mm(cn_r,torch.t(self.lrmat)).mul(cn_l))

		l_in_mat = torch.cat(l_in_mat).to(self.device)
		r_in_mat = torch.cat(r_in_mat).to(self.device)

		return l_in_mat,r_in_mat

def load_data(args,nbr_size,batch_size,device):

	fname = args.home+args.input+args.raw_data
	l_fname = fname.replace(".pkl",".ligands.pkl")
	r_fname = fname.replace(".pkl",".receptors.pkl")
	lr_fname = fname.replace(".pkl",".ligands_receptors_mat_815_780.pkl")

	df_h = pd.read_csv(args.home+args.output+args.nbr_model["out"]+args.nbr_model["mfile"]+"etm_hh_data.tsv",sep="\t")

	df_l = pd.read_pickle(l_fname)
	df_r = pd.read_pickle(r_fname)
	df_l = df_l[df_l["index"].isin(df_h["cell"].values)]
	df_r = df_r[df_r["index"].isin(df_h["cell"].values)]

	dfjoin = pd.merge(df_l["index"],df_h,how="left",left_on="index",right_on="cell")
	model_ann = ApproxNN(dfjoin.iloc[:,2:].to_numpy(), dfjoin.iloc[:,0].values)
	model_ann.build()

	h_mat = torch.tensor(dfjoin.iloc[:,2:].values.astype(np.float32)).to(device)
	lmat = torch.tensor(df_l.iloc[:,1:].values.astype(np.float32)).to(device)
	rmat = torch.tensor(df_r.iloc[:,1:].values.astype(np.float32)).to(device)
	lrlabels = df_l.iloc[:,0].values

	df_lr = pd.read_pickle(lr_fname)
	df_lr = df_lr.loc[df_l.columns[1:],df_r.columns[1:]]
	Alr = torch.tensor(df_lr.values.astype(np.float32)).to(device)

	return DataLoader(LRDataset(lmat,rmat,lrlabels,Alr,model_ann,nbr_size,h_mat,device), batch_size=batch_size, shuffle=True)

def reparameterize(mean,lnvar):
	sig = torch.exp(lnvar/2.)
	eps = torch.randn_like(sig)
	return eps.mul_(sig).add_(mean)

def etm_llik(xx,pr, eps=1e-8):
	return torch.sum(xx * torch.log(pr+eps),dim=-1)

def kl_loss(mean,lnvar):
	return  -0.5 * torch.sum(1. + lnvar - torch.pow(mean,2) - torch.exp(lnvar), dim=-1)

class Stacklayers(nn.Module):
	def __init__(self,input_size,layers):
		super(Stacklayers, self).__init__()
		self.layers = nn.ModuleList()
		self.input_size = input_size
		for next_l in layers:
			self.layers.append(nn.Linear(self.input_size,next_l))
			self.layers.append(self.get_activation())
			nn.BatchNorm1d(next_l)
			self.input_size = next_l
		
	def forward(self, input_data):
		for layer in self.layers:
			input_data = layer(input_data)
		return input_data

	def get_activation(self):
		return nn.ReLU()

class BridgeEncoder(nn.Module):
	def __init__(self, input_dims, latent_dims):
		super(BridgeEncoder, self).__init__()
		self.linear = nn.Linear(input_dims,latent_dims)
		nn.ReLU()
		nn.BatchNorm1d(latent_dims)

	def forward(self, x):
		return F.relu(self.linear(x))

class ETMEncoder(nn.Module):
	def __init__(self,input_dims1, input_dims2,latent_dims,layers1,layers2):
		super(ETMEncoder, self).__init__()
		self.fc1 = Stacklayers(input_dims1,layers1)
		self.fc2 = Stacklayers(input_dims2,layers2)
		self.fc = BridgeEncoder(latent_dims+latent_dims,latent_dims)
		self.z_mean = nn.Linear(latent_dims,latent_dims)
		self.z_lnvar = nn.Linear(latent_dims,latent_dims)

	def forward(self, xx1, xx2):
		xx1 = xx1/torch.sum(xx1,dim=-1,keepdim=True)
		xx2 = xx2/torch.sum(xx2,dim=-1,keepdim=True)
		ss1 = self.fc1(torch.log1p(xx1))
		ss2 = self.fc2(torch.log1p(xx2))

		ss = self.fc(torch.cat((ss1,ss2),1))

		mm = self.z_mean(ss)
		lv = torch.clamp(self.z_lnvar(ss),-4.0,4.0)
		z = reparameterize(mm,lv)
		return z, mm,lv

class ETMDecoder(nn.Module):
	def __init__(self,latent_dims,out_dims1, out_dims2,jitter=.1):
		super(ETMDecoder, self).__init__()
		self.lbeta1= nn.Parameter(torch.randn(latent_dims,out_dims1)*jitter)
		self.lbeta2= nn.Parameter(torch.randn(latent_dims,out_dims2)*jitter)
		self.beta = nn.LogSoftmax(dim=-1)
		self.hid = nn.LogSoftmax(dim=-1)

	def forward(self, zz):
		beta1 = self.beta(self.lbeta1)
		beta2 = self.beta(self.lbeta2)

		hh = self.hid(zz)

		beta = torch.cat((beta1,beta2),1)

		return torch.mm(torch.exp(hh),torch.exp(beta)), hh

class ETM(nn.Module):
	def __init__(self,input_dims1,input_dims2,latent_dims,layers1, layers2) :
		super(ETM,self).__init__()
		self.encoder = ETMEncoder(input_dims1,input_dims2,latent_dims,layers1,layers2)
		self.decoder = ETMDecoder(latent_dims, input_dims1, input_dims2)
		
	def forward(self,xx1,xx2):
		zz,m,v = self.encoder(xx1,xx2)
		pr,h = self.decoder(zz)
		return pr,m,v,h
	
def train(etm, data, device, epochs,l_rate):
	logger.info("Starting training....")
	opt = torch.optim.Adam(etm.parameters(),lr=l_rate)
	loss_values = []
	for epoch in range(epochs):
		loss = 0
		r = 0
		for x1,x2 in data:
			x1 = x1.reshape(x1.shape[0]*x1.shape[1],x1.shape[2])
			x2 = x2.reshape(x2.shape[0]*x2.shape[1],x2.shape[2])
			opt.zero_grad()
			recon,m,v,h = etm(x1,x2)
			x = torch.cat((x1,x2),1)
			loglikloss = etm_llik(x,recon)
			kl = kl_loss(m,v)
			train_loss = torch.mean(kl-loglikloss).to("cpu")
			train_loss.backward()
			opt.step()
			loss += train_loss.item()
			r += 1
			print(epoch,r)
		logger.info('====> Epoch: {} Average loss: {:.4f}'.format(epoch, loss/len(data)))
		
		loss_values.append(loss/len(data))
	
	return loss_values

def get_latent(data,model,model_file,loss_values):
	import matplotlib.pylab as plt

	for xx1,xx2 in data: break
	zz,m,v = model.encoder(xx1,xx2)
	pr,hh = model.decoder(zz)
	hh = torch.exp(hh)

	df_z = pd.DataFrame(zz.to('cpu').detach().numpy())
	df_z.columns = ["zz"+str(i)for i in df_z.columns]
	df_z.to_csv(model_file+"etm_zz_data.csv",sep="\t",index=False)

	df_h = pd.DataFrame(hh.to('cpu').detach().numpy())
	df_h.columns = ["hh"+str(i)for i in df_h.columns]
	df_h.to_csv(model_file+"etm_hh_data.csv",sep="\t",index=False)

	beta1 =  None
	beta2 =  None
	for n,p in model.named_parameters():
		if n == "decoder.lbeta1":
			beta1=p
		elif n == "decoder.lbeta2":
			beta2=p
	beta_smax = nn.LogSoftmax(dim=-1)
	beta1 = torch.exp(beta_smax(beta1))
	beta2 = torch.exp(beta_smax(beta2))

	df_beta1 = pd.DataFrame(beta1.to('cpu').detach().numpy())
	df_beta1.to_csv(model_file+"etm_beta1_data.csv",sep="\t",index=False)

	df_beta2 = pd.DataFrame(beta2.to('cpu').detach().numpy())
	df_beta2.to_csv(model_file+"etm_beta2_data.csv",sep="\t",index=False)

	plt.plot(loss_values)
	plt.ylabel("loss", fontsize=18)
	plt.xlabel("epochs", fontsize=22)
	plt.savefig(model_file+"loss.png");plt.close()
