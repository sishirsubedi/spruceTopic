import os 
import sys
import datetime
from util._io import read_config
from collections import namedtuple
from analysis import _topics,_umap_viz
import logging
import pandas as pd
import spruce
import torch

mode= sys.argv[1]
now = datetime.datetime.now()
# args_home = '/home/BCCRC.CA/ssubedi/projects/experiments/spruce_topic/0_augmented_cell_topic_v_beta/'
args_home = '/home/sishirsubedi/projects/experiments/spruce_topic/0_augmented_cell_topic_v_beta/'

params = read_config(args_home+'config/bcmix.yaml')
args = namedtuple('Struct',params.keys())(*params.values())


if mode =='train':
	model_info = args_home+args.output+args.cell_topic['out']+args.cell_topic['model_info']
	id = now.strftime('%Y%m%d')
	model_id = model_info+'_'+id


	logging.basicConfig(filename=model_id+'.log',
					format='%(asctime)s %(levelname)-8s %(message)s',
					level=logging.INFO,
					datefmt='%Y-%m-%d %H:%M:%S')

	sp = spruce.Spruce()
	sp.data.sparse_data = args.home + args.input + args.sparse_data 
	sp.data.sparse_data_ids = args.home + args.input + args.sparse_data_ids
	sp.model_id = model_id

	batch_size = args.cell_topic['train']['batch_size']
	l_rate = args.cell_topic['train']['l_rate']
	epochs = args.cell_topic['train']['epochs']
	layers = args.cell_topic['train']['layers']
	latent_dims = args.cell_topic['train']['latent_dims']
	device = args.cell_topic['train']['device']

	loss_values = sp.run_cell_topic(batch_size,l_rate,epochs,layers,latent_dims,device)
	torch.save(sp.cell_topic.model.state_dict(), sp.model_id + '_cell_topic.torch')
	dflv = pd.DataFrame(loss_values[0])
	dflv.to_csv(sp.model_id + '_cell_topic_loss.txt.gz',index=False,compression='gzip')
	dflv = pd.DataFrame(loss_values[1])
	dflv.to_csv(sp.model_id + '_cell_topic_loss2.txt.gz',index=False,compression='gzip')

elif mode=='eval':
	sp = spruce.Spruce()
	sp.data.sparse_data = args.home + args.input + args.sparse_data 
	sp.data.sparse_data_ids = args.home + args.input + args.sparse_data_ids
	sp.model_id = args_home+args.output+args.cell_topic['out']+args.cell_topic['model_info']+args.cell_topic['model_id']

	sp.cell_topic.model = torch.load(sp.model_id + '_cell_topic.torch')
	batch_size = args.cell_topic['eval']['batch_size']
	layers = args.cell_topic['train']['layers']
	latent_dims = args.cell_topic['train']['latent_dims']
	device = 'cpu'
	df_z,df_h,df_beta,df_beta_var = sp.eval_cell_topic(batch_size,layers,latent_dims,device)
	df_z.to_csv(sp.model_id+'_cell_topic_z.tsv.gz',sep='\t',index=False,compression='gzip')
	df_h.to_csv(sp.model_id+'_cell_topic_h.tsv.gz',sep='\t',index=False,compression='gzip')
	df_beta.to_csv(sp.model_id+'_cell_topic_beta.tsv.gz',sep='\t',index=False,compression='gzip')
	df_beta_var.to_csv(sp.model_id+'_cell_topic_beta_var.tsv.gz',sep='\t',index=False,compression='gzip')

elif mode=='plots':

	sp = spruce.Spruce()
	sp.model_id = args.home+args.experiment+args.output+args.cell_topic['out']+args.cell_topic['model_info']+args.cell_topic['model_id']	
	 
	sp.data.raw_data_genes = pd.read_pickle(args.home+args.input+args.raw_data_genes)[0].values

	sp.cell_topic.beta = pd.read_csv(sp.model_id+'_cell_topic_beta.tsv.gz',sep='\t',compression='gzip')


	sp.cell_topic.z = pd.read_csv(sp.model_id+'_cell_topic_z.tsv.gz',sep='\t',compression='gzip')
	sp.cell_topic.h = pd.read_csv(sp.model_id+'_cell_topic_h.tsv.gz',sep='\t',compression='gzip')

	print('processing...',sp.model_id)
	_umap_viz.plot_umap_with_annotation_mix(sp)
	# _topics.topic_top_genes(sp,5)
	# _topics.topic_top_genes(sp,10)
	# _topics.topic_top_genes(sp,25)
	# _topics.sample_cells_with_latent(sp)
	# _umap_viz.plot_umap(sp)
