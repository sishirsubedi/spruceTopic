import pandas as pd
import numpy as np
import preprocess 
import component_check 
from dlearn import etm
from dlearn import ae
import importlib

data="cd4_cd8_500cells_per_tissue_counts.txt.gz"
# data="lda_test_data.txt"
df = pd.read_csv("../output/"+data,sep="\t")
df = df[ ["cell"]+\
        [x for x in df.columns if x not in["cell","sample"]]+\
        ["sample"]]
df = preprocess.filter_minimal(df)

y = np.array([1 if "CD4" in x else 0 for x in df.iloc[:,-1]])
# y = pd.factorize(df.iloc[:,-1])[0]

# component_check.run_component_analysis(df.iloc[:,1:df.shape[1]-1],y,"pca")

#### etm tests
device = etm.torch.device('cuda' if etm.torch.cuda.is_available() else 'cpu')
input_dims = df.iloc[:,1:-1].shape[1]
layers = [128,16]
latent_dims = 16

model = etm.ETM(input_dims,input_dims,latent_dims,layers).to(device)
data = etm.load_data(df.iloc[:,1:-1].to_numpy(),y,device)
print(model)
model = etm.train(model,data,device)



#### ae tests
# device = ae.torch.device('cuda' if ae.torch.cuda.is_available() else 'cpu')
# input_dims = df.iloc[:,1:-1].shape[1]
# latent_dims = 32

# autoencoder = ae.Autoencoder(input_dims,latent_dims).to(device)
# data = ae.load_data(df.iloc[:,1:-1].to_numpy(),y,device)
# autoencoder = ae.train(autoencoder,data,device)
# ae.plot_ae_components(data,autoencoder,device,"c13_18_all_ae")