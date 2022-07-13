from audioop import add
import os
from turtle import title, width
import pandas as pd
import numpy as np
import igraph
import seaborn as sns



def cell_interaction_network(spr,df):
	import matplotlib.pylab as plt
	plt.rcParams['figure.figsize'] = [15, 10]
	plt.rcParams['figure.autolayout'] = True
	import colorcet as cc
	import seaborn as sns


	# plt.rcParams['figure.figsize'] = [40,10]
	# plt.rcParams['figure.autolayout'] = True


	dfs = df.groupby('cluster', group_keys=False).apply(pd.DataFrame.sample,frac=0.1)

	cells = [x for x in list(dfs['cluster_celltype'].values)]

	# dfs['cluster'] = [str(x)+'-'+y for x,y in zip(dfs['cluster'],dfs['cluster_celltype'])]
	# cells = [x for x in list(dfs['cluster'].values)]

	states = ['interact_topic'+str(int(x)) for x in dfs['interact_topic'].unique()]
	print(states)

	## construct graph
	# if len(states)<=10:
	# 	colors = sns.color_palette("Paired")
	# elif len(states)>10:
	# colors = sns.color_palette('tab10',len(cells))
	colors = sns.color_palette(cc.glasbey_dark, n_colors=len(cells))
	cell_clr = {}
	for i,c in enumerate(cells): cell_clr[c]=colors[i]

	g = igraph.Graph()
	g.add_vertices(cells+states)

	gedges = []
	for i,row in dfs.iterrows():
		cell = row.cluster_celltype
		s = int(row['interact_topic'])
		interaction_state = 'interact_topic'+str(s)
		epair = cell + '_' + interaction_state

		if epair not in gedges:
			g.add_edge(cell,interaction_state,weight=0.01,color=cell_clr[cell])
			gedges.append(epair)
		else:
			eid = g.get_eid(cell,interaction_state)
			g.es[eid]['weight'] += 0.01


	to_delete_eids = [e.index for e in g.es if e['weight']<10]
	g.delete_edges(to_delete_eids)

	to_delete_vids = [v.index for v in g.vs if v.degree()<1]
	g.delete_vertices(to_delete_vids)

	
	for v in g.vs:
		if "state" not in v['name']: 
			v['attr'] = 'cell'
			v['size'] = 10
			v['color'] = 'white'
			v['shape'] = 'circle'
		else: 
			v['attr'] = 'interact_topic'
			v['size'] = 10
			v['color'] = 'lightyellow'
			v['shape'] = 'white'
		

	visual_style={}
	visual_style["vertex_label"] = [ x.replace('interact_topic','s') for x in g.vs["name"]]
	# visual_style["vertex_size"] = g.vs['size']
	# visual_style["vertex_color"] = g.vs['color']
	visual_style["vertex_label_size"] = 20
	visual_style["edge_color"] = g.es['color']
	visual_style["edge_width"] = [x/10 for x in g.es['weight']]
	# visual_style["layout"] = g.layout_reingold_tilford_circular()
	visual_style["layout"] = g.layout_circle()
	visual_style["bbox"] = (1000, 1000)

	igraph.plot(g, target=spr.interaction_topic.model_id+"_it_ccview_network_plot.png",**visual_style,margin=40)

def interaction_statewise_lr_network(spr,states,top_lr=200,keep_db=True,df_db=None):

	import matplotlib.pylab as plt
	import colorcet as cc
	import seaborn as sns
	plt.rcParams['figure.figsize'] = [20,10]
	plt.rcParams['figure.autolayout'] = True

	fig, ax = plt.subplots(2,4) 
	ax = ax.ravel()

	ligands = list(spr.interaction_topic.beta_r.columns) 
	receptors = list(spr.interaction_topic.beta_l.columns) 

	for i,state in enumerate(states):


		l_vals =  spr.interaction_topic.beta_r.iloc[state,:].values
		r_vals =  spr.interaction_topic.beta_l.iloc[state,:].values

		l = l_vals.reshape(l_vals.shape[0],1)
		r = r_vals.reshape(r_vals.shape[0],1)
		r = r.T
		lr = l[:,None]+r
		lr = lr.flatten()
		lr = lr[lr.argsort()]
		cuttoff = lr[-top_lr:][0]
		print('cuttoff is...'+str(cuttoff))

		
		g = igraph.Graph()

		for li,ligand in enumerate(ligands):
			for ri,receptor in enumerate(receptors):
				w = l_vals[li]+r_vals[ri]
				if w>cuttoff:
					g.add_vertex(ligand)
					g.add_vertex(receptor)
					g.add_edge(ligand,receptor,weight= w)
		

		lrpair = {}
		for lr_p in df_db['lr_pair']:
			l,r = lr_p.split('_')[0],lr_p.split('_')[1]
			if r in lrpair.keys():
				lrpair[r].append(l)
			else:
				lrpair[r] = [l]

		keep_eids = []
		if keep_db:
			for e in g.es:
				source = g.vs[e.source]['name']
				target = g.vs[e.target]['name']
				if (source in lrpair.keys() and target in lrpair[source] ) or (target in lrpair.keys() and source in lrpair[target] ) :
					keep_eids.append(e.index)
					print(source,target)
		else:
			for e in g.es:
				source = g.vs[e.source]['name']
				target = g.vs[e.target]['name']
				if (target in lrpair.keys() and source not in lrpair[target] ):
					keep_eids.append(e.index)
					print(source,target)
		
		to_delete_eids = [e.index for e in g.es if e.index not in keep_eids]
		g.delete_edges(to_delete_eids)

		to_delete_vids = [v.index for v in g.vs if v.degree()<1]
		g.delete_vertices(to_delete_vids)

		for v in g.vs:
			if v['name'] in receptors: 
				v['attr'] = 'receptor'
				v['size'] = 15
				v['color'] = 'r'
				v['shape'] = 'diamond'
			else: 
				v['attr'] = 'ligand'
				v['size'] = 10
				v['color'] = 'b'
				v['shape'] = 'square'
			

		visual_style={}
		visual_style["vertex_label"] =  g.vs['name']
		visual_style["vertex_size"] = g.vs['size']
		visual_style["vertex_color"] = g.vs['color']
		visual_style["vertex_label_size"] = 14
		# visual_style["edge_width"] = [x/5 for x in g.es['weight']]
		visual_style["layout"] = g.layout_circle()

		if len(g.vs) > 0:
			ax[i].set_axis_off()
			ax[i].set_title('interaction topic_'+str(state))
			igraph.plot(g,target=ax[i],**visual_style,margin=20,title='interaction topic_'+str(state))
			# igraph.plot(g, target=spr.interaction_topic.model_id+'_lr_network_it_state_'+str(state)+'.png',**visual_style,margin=40,)
	flag='not_db'
	if keep_db: flag='db'
	plt.savefig(spr.interaction_topic.model_id+'_lr_network_it_states_'+flag+'.png');plt.close()

def lr_correlation_network(spr,df,interact_topics,zcutoff,corr_th):

	import matplotlib.pylab as plt
	import networkx as nx
	import colorcet as cc
	import seaborn as sns
	import scipy.stats as stats

	plt.rcParams['figure.figsize'] = [30,20]
	plt.rcParams['figure.autolayout'] = True

	fig, ax = plt.subplots(2,3) 
	ax = ax.ravel()


	for i,topic in enumerate(interact_topics):

		r_vals = spr.interaction_topic.beta_r.iloc[topic,:]
		receptors = r_vals[stats.zscore(r_vals)>zcutoff].index.values
		l_vals = spr.interaction_topic.beta_l.iloc[topic,:]
		ligands = l_vals[stats.zscore(l_vals)>zcutoff].index.values

		# receptors = list(spr.interaction_topic.beta_r.iloc[topic,:].sort_values(ascending=False).head(300).index)
		# ligands = list(spr.interaction_topic.beta_l.iloc[topic,:].sort_values(ascending=False).head(300).index)
		all_genes = np.concatenate([ligands,receptors])

		df_gexp = spr.data.raw_data.loc[:,np.concatenate([['index'],all_genes])].copy()
		df_gexp = df_gexp.replace(to_replace = 0, value = 10)

		cancer_cells = df[df['interact_topic']==topic]['cancer_cell'].unique()
		nbr_cells = df[df['interact_topic']==topic]['nbr'].unique()
		all_cells = np.concatenate( [cancer_cells , nbr_cells])

		df_gexp_topic = df_gexp[df_gexp['index'].isin(all_cells)].copy()
		df_gexp_topic.index = df_gexp_topic['index']
		df_gexp_topic = df_gexp_topic.drop(columns=['index'])	
		df_gexp_topic = df_gexp_topic.T

		df_corr = pd.DataFrame(np.corrcoef(df_gexp_topic))
		df_corr.index = all_genes
		df_corr.columns = all_genes
		
		df_corr = df_corr.reset_index().melt(id_vars=['index'])
		df_corr.columns = ['gene1','gene2','c']

		df_corr = df_corr[df_corr['c']>corr_th[topic]]
		
		g = nx.Graph()

		for idx,row in df_corr.iterrows():
			g1 = row['gene1']
			g2 = row['gene2']
			# if (g1 in ligands and g2 in receptors) or (g1 in receptors and g2 in ligands):
			if g1 ==g2 :continue
			g.add_node(row['gene1'])
			g.add_node(row['gene2'])
			g.add_edge(row['gene1'],row['gene2'],weight= row['c'])


		remove = [node for node, degree in g.degree() if degree < 2]
		g.remove_nodes_from(remove)

		edges = g.edges()
		weights = [ g[u][v]['weight'] * 10 for u,v in edges]
		if len(g.nodes()) > 0:
			fs = 12	
			# if topic ==18 : fs = 6
			ax[i].set_axis_off()
			ax[i].set_title(str(topic),fontsize=20)
			color_map = ['salmon' if node in receptors else 'darkcyan' for node in g]
			pos = nx.circular_layout(g,scale=2)
			nx.draw(g,pos=pos,with_labels=False,ax=ax[i],node_color=color_map,edge_color='grey',width=weights)
			# nx.draw(g,pos=pos,with_labels=False,ax=ax[i],node_color=color_map,edge_color='grey')
			pos_attrs = {}
			adj = 0.15
			for node, coords in pos.items():
				if coords[0] > 0 and coords[1] > 0:
					pos_attrs[node] = (coords[0], coords[1] + adj)
				elif coords[0] < 0 and coords[1] < 0:
					pos_attrs[node] = (coords[0], coords[1] - adj)
				elif coords[0] > 0 and coords[1] < 0:
					pos_attrs[node] = (coords[0], coords[1] - adj)
				elif coords[0] < 0 and coords[1] > 0:
					pos_attrs[node] = (coords[0], coords[1] + adj)

			nx.draw_networkx_labels(g, pos_attrs,ax=ax[i],font_size=fs,font_weight='bold')


	plt.savefig(spr.interaction_topic.model_id+'_lr_network_it_topics_corr.pdf');plt.close()
