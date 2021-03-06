# -*- coding: utf-8 -*-
"""
Created on Sat Feb 27 19:24:07 2021
@author: SURFACE
essai d'optimisation avec scipy
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import cvxpy as cvx
from scipy.optimize import differential_evolution, LinearConstraint
from sklearn.model_selection import train_test_split
from scipy.linalg import sqrtm
from random import seed

seed(3)

pays_ocde = {"Germany" :'DEU',"Australia" :'AUS',"Austria":'AUT',"Belgium":'BEL',"Canada":'CAN',"Denmark":'DNK',"Spain":'ESP',
             "Finland":'FIN',"France":'FRA',"Hungary":'HUN',"Ireland":'IRL', "Iceland": 'ISL', "Italy":'ITA', 'Korea': 'KOR',
             "Japan":'JPN',"Luxembourg":'LUX',"Norway":'NOR',"New-Zealand":'NZL',"Netherlands":'NLD',"Portugal":'PRT',
             "United Kingdom":'GBR',"Sweden":'SWE',"Switzerland":'CHE',"Slovak Republic":'SVK',"United-States":'USA'}

variables = ['Actifs', 'Chomage', 'Conso', 'Emplois', 'Exports', 'Formation', 'PIB']

#Note pour prendre le second niveau d'un multiindex : 
#df_cs.xs('PIB', axis=1, level=1, drop_level=False)

#On importe les données
data = pd.read_csv(r'df_countries.csv', header=[0,1])
data = data.set_index('Variable')


# Pour répliquer le papier, il faut retirer la Grèce et la Turquie

#On supprime les inégalités qui ne nous intéressent pas pour l'instant.

# Partie non nécessaire pour data2
# for i in pays_ocde.values() :
#    data= data.drop([(i,'income p0p50'),(i,'income p90p100')], axis=1)


#On trie les données pour améliorer les performances et éviter les warnings:
data = data.sort_index(axis=1)
  
#on créé le dataframe qui nous intéresse qui est de la forme : pays en colonnes, 
#année + variable en ligne (une ligne est donc la valeur d'une variable, pour une 
#année donnée dans chaque pays)

df_ct = pd.DataFrame()
for i in variables :
    interm = data.xs(str(i), axis=1, level=1, drop_level=True)   #On prend uniquement les colonnes qui se rapporte à une variable avec .xs
    interm = interm.drop(0, axis=0)                                #On enlève la ligne d'indice 0 qui est vide (seulement des nan)
    interm['Variables'] = str(i)                                    #on rajoute une colonne "variables" qui nous servira plus tard pour construire le problème d'optimisation
    df_ct = pd.concat([df_ct, interm], axis=0)                      #On concatène le df ainsi créé avec les autres


df_ct.rename(columns=pays_ocde, inplace=True)
df_ct.drop(list(d for d in range(1, 20)), inplace=True) # On commence en 1995

df_ct2 = df_ct[df_ct["Variables"].isin(['PIB', 'Actifs', 'Emplois'])].dropna()

# Nous créons aussi un df pour calculer les moyennes agrégées requises

data_mean = data.copy()
for pays in pays_ocde.keys():
   data_mean[pays] = data_mean[pays].assign(Conso=lambda x: x.Conso / x.PIB)

data_mean.rename(columns={'Conso': 'Conso_share'}, inplace=True)

for pays in pays_ocde.keys():
    data_mean[pays] = data_mean[pays].assign(Emplois=lambda x: np.log(x.PIB/x.Emplois) - np.log(x.PIB.shift()/x.Emplois.shift()))

data_mean.rename(columns={'Emplois': 'Prod_growth'}, inplace=True)

for i in pays_ocde.keys() :
    data_mean=data_mean.drop([(i,'PIB'),(i,'Actifs')], axis=1)
    
df_ct_mean = pd.DataFrame()
for i in ['Chomage', 'Conso_share', 'Prod_growth','Exports', 'Formation']:
    interm = data_mean.xs(str(i), axis=1, level=1, drop_level=True)   #On prend uniquement les colonnes qui se rapporte à une variable avec .xs
    interm = interm.drop(0, axis=0)                                #On enlève la ligne d'indice 0 qui est vide (seulement des nan)
    interm['Variables'] = str(i)                                    #on rajoute une colonne "variables" qui nous servira plus tard pour construire le problème d'optimisation
    df_ct_mean = pd.concat([df_ct_mean, interm], axis=0)

df_ct_mean.rename(columns=pays_ocde, inplace=True)

# df_ct_mean.drop(list(d for d in range(1,102)), inplace=True)
# df_ct_mean.drop(list(d for d in range(106,120)), inplace=True)

# df_ct2[df_ct2["Variables"]=="PIB"]['USA']

# On mesure le PIB en déviation par rapport à l'année 1995
for var in ['PIB', 'Actifs', 'Emplois']:    
    for pays in df_ct2.drop('Variables', 1).columns:    
        df_ct2[df_ct2["Variables"]==var] = df_ct2[df_ct2["Variables"]==var].assign(**{pays: lambda x: (x[pays] - x[pays].iloc[0]) / x[pays].iloc[0]})


#On créé les matrices pour la formulation du problème :
'''  
Cette partie est le code d'origine, on s'en sert pour la modélisation qui suit
 
X1 = df_ct.dropna()[['USA','Variables']]          #On créé le vecteur que l'on veut approcher X1
X1 = X1.drop(list(d for d in range (109,120)))              #On supprimme les lignes avec des indices entre 109 et 121 (qui correspondent aux années après 2016)
X1 = X1[X1.Variables != 'PIB'].drop('Variables', axis=1)   #On ne garde que les variables et pas le PIB
X1 = X1.to_numpy()                                          #On passe en tableau Numpy
#On réitère le même processus mais cette fois avec le reste des pays
X0 = df_ct.dropna().drop('USA', axis=1)
X0 = X0.drop(list(d for d in range (109,120)))
X0 = X0[X0.Variables != 'PIB'].drop('Variables',axis = 1)
X0 = X0.to_numpy()
'''

# Modélisation avec la moyenne sur la période pré-intervention

np.set_printoptions(suppress=True) # Pcq relou les notations avec exponentielles

X1 = df_ct2[['USA', 'Variables']]
X1 = X1.drop(list(d for d in range(109,120)))
X1_mean = df_ct_mean[['USA', 'Variables']].groupby('Variables').mean().reset_index()
X1 = pd.concat([X1, X1_mean]).reset_index().drop(['index', 'Variables'], 1)
X1 = X1.values

# Notons que X1 n'a aucune valeur manquante, il va falloir en retirer pour
# correspondre à X0 qui, lui, en aura

X0 = df_ct2.drop('USA', 1)
X0 = X0.drop(list(d for d in range(109,120)))
X0_mean = df_ct_mean.drop('USA', 1).groupby('Variables').mean().reset_index()
X0 = pd.concat([X0, X0_mean]).reset_index().drop(['index', 'Variables'], 1)
X0 = X0.values


# On construit et on "résout" le problème cvxpy

x = cvx.Variable((24,1),nonneg=True)                #On définit un vecteur de variables cvxpy
cost = cvx.norm(X1 - X0@x, p=2)                     #on définit la fonction de cout : norme des résidus
constraints = [x>=0, cvx.sum(x)==1]                     #La contrainte
prob = cvx.Problem(cvx.Minimize(cost), constraints)  #On définit le problème
prob.solve()                                        #On le résout

x_solve = x.value
#https://stackoverflow.com/questions/65526377/cvxpy-returns-infeasible-inaccurate-on-quadratic-programming-optimization-proble 
#explication de pourquoi avec sum_square ça ne fonctionnait pas

#Print result

print("\nThe optimal value is", prob.value)
print("The optimal x is")
print(x.value)
print("The norm of the residual is ", cvx.norm(X0@x - X1, p=2).value)

#Partie pour trouver le V : 
#Dans leur papier, les auteurs disent qu'ils prennent le V qui minimisent
#l'erreur de prédiction du modèle.
#On va diviser en deux le data set afin 
#On définit un problème cvxpy avec V en paramètre pour accélérer le processus :

X0_train,X0_test,X1_train,X1_test = train_test_split(X0,X1,test_size=0.2)

V_sqrt = cvx.Parameter((123,123))
x = cvx.Variable((24,1),nonneg=True)                        #On définit un vecteur de variables cvxpy
cost = cvx.norm(V_sqrt@(X1_train - X0_train@x), p=2)        #on définit la fonction de cout : norme des résidus
#cost = cvx.sum(V_sqrt @ cvx.square(X1_train - X0_train@x))
constraints = [cvx.sum(x)==1]                               #La contrainte
prob = cvx.Problem(cvx.Minimize(cost), constraints)         #On définit le problème

def loss_V(V):
    #V_sqrt sera mis au carré donc on dois toujours mettre dans celui ci 
    #la racine de V
    V_sqrt.value = np.diag(V)
    prob.solve()
    #print(((X1_test - X0_test @ x.value).T@(X1_test - X0_test @ x.value))[0,0])
    return(((X1_test - X0_test @ x.value).T@(X1_test - X0_test @ x.value))[0,0])

def diffevo_optimize():
    #Uses the differential evolution optimizer from scipy to solve for synthetic control
    
    contrainte = LinearConstraint(np.ones((1,123)), 1, 1)
    bounds = [(0,1) for i in range(123)]
    result = differential_evolution(loss_V,bounds,maxiter=1,constraints=contrainte)
        
    V = result.x
        
    return V


# Visualisation (ATTENTION NON MODIFIEE)

# Voici la table des coefficients attribués à chaque pays
pd.set_option('display.float_format', lambda x: '%.3f' % x)
# Parce que là aussi les notations expo rendent les résultats illisibles

country_list = df_ct.dropna().drop(['USA', 'Variables'], axis=1)
coeff = pd.DataFrame(x.value, index=country_list.columns)
print(coeff)


# Commençons par visualiser l'écart de tendance en PIB

df_pib = df_ct2[df_ct2["Variables"]=="PIB"]
#df_pib.drop(df_pib.columns.difference(['USA', 'GBR', 'AUS', 'DNK', 'ISL', 'IRL', 'JPN', 'KOR', 'NLD', 'PRT']), 1, inplace=True)
#df_pib = df_pib.dropna()
df_pib = df_pib.reset_index().drop('index', 1)

sc = df_pib.drop(['Variables','USA'],axis = 1)@ x.value

#df_pib[('USA')].plot(label='USA')
#sc.plot(label="Contrôle Synthétique")
plt.plot(df_pib[('USA')])
plt.plot(sc)
plt.vlines(84, 0, 1, linestyle = '--', color = 'red', label = 'Election de Trump')
plt.legend()
plt.show()

'''
Nous remarquons que le modèle est loin de reproduire la réalité, d'autant plus
que les coefficients de pondérations donnés par le papier de Born (2020) ne 
sont pas les mêmes. Nous allons alors passer à la validation croisée pour 
essayer de régler ces problèmes.
'''