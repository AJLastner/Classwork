# -*- coding: utf-8 -*-
"""
Created on Wed Apr 24 17:56:13 2024

@author: alastner
"""

# import all the important things
import numpy as np
import pandas as pd
import keras
from sklearn.model_selection import train_test_split
import keras_tuner
import matplotlib.pyplot as plt

#%%

# url to dataset
url = "https://umd.box.com/shared/static/2jle19cmbowbfmroegnxld7xu8wpc5t7.csv"
# read dataset from url
df = pd.read_csv(url,dtype={'median_phenophase': 'float64','L1':'string','L2':'string','L3':'string'})

# post-preprocessing preprocessing (final stage of precprocessing not done in MATLAB)
# drop unused columns (unused phenofeatures + unused land cover + unused ecoregion levels)
df = df.drop(['midgreenup','midgreendown','min_phenophase','median_phenophase','IGBP_class','PFT_class','L2','L3'], axis=1)
# drop sites with relatively complex phenocycles
df = df.drop(df[df.max_phenophase > 1].index)
df = df.drop(['max_phenophase'], axis=1)
# drop sites in lakes
df = df.drop(df[df.L1 == "0"].index)
# drop sites with crops or little vegetation cover
df = df.drop(df[(df.UMD_class == any([12,13,15]))].index)
# drop sites wiwh null values
df = df.dropna()
# reset index
df = df.reset_index()

#%%

# set a random seed for reproducibility
np.random.seed(144)

###CODE TESTING SPLIT
#dfx = df.sample(10000000) # 10 million

# pull phenofeatures of interest as features
# start and end of greenup, start and end of senescence (browndown), and peak
# correct for dates going over one year (loop back around)
X = df[["greenup","maturity","senescence","dormancy","peak","latitude","longitude"]]
X[X[["greenup","maturity","senescence","dormancy","peak"]] > 365] = X[X[["greenup","maturity","senescence","dormancy","peak"]] > 365] - 365
# normalize
X[["greenup","maturity","senescence","dormancy","peak"]] = X[["greenup","maturity","senescence","dormancy","peak"]].div(365)
# pull level 1 ecoregion as labels
Y = df[["L1"]]
Y = pd.get_dummies(pd.Series(Y['L1'].tolist()),dtype=int)
Y = Y[["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15"]]

# split dataset into training and testing sets (50%/50%)
pheno_train, pheno_test, eco_train, eco_test = train_test_split(
    X,Y,random_state=144,test_size=0.50,shuffle=True)

latlon_test = pheno_test[["latitude","longitude"]]
pheno_test = pheno_test[["greenup","maturity","senescence","dormancy","peak"]]
pheno_train = pheno_train[["greenup","maturity","senescence","dormancy","peak"]]

# check relative proportion of ecoregions
##eco_train = pd.get_dummies(pd.Series(eco_train['L1'].tolist()),dtype=int)
##eco_test = pd.get_dummies(pd.Series(eco_test['L1'].tolist()),dtype=int)
frequency = Y.sum(axis=0)
frequency

# split training into training and validation sets (75%/25%)
##pheno_train, pheno_val, eco_train, eco_val = train_test_split(pheno_train,eco_train,random_state=144,test_size=0.25,shuffle=True)

#%%
"""
# create class weights
# <weight = most prevelent label / (label of interest^0.5 * most prevelent label^0.5)>
# weight = (label of interest^0.5 / most prevelent label^0.5)*0.01
cw = {}
m = frequency[(frequency.keys())[0]]
n = 0
for key in frequency:
  #cw[n] = m/((key**0.5)*(m**0.5))
  cw[n] = (( (m**0.5)/(key**0.5) ) * 0.01)**0.5
  n = n + 1

cw
"""
#%%
#Plot frequency and class weights

import seaborn as sns

ax = sns.barplot(frequency)
ax.set(xlabel='Ecoregion', ylabel='Frequency')
ax.set(yscale="log")
plt.show()
"""
ax = sns.barplot(cw)
ax.set(xlabel='Ecoregion', ylabel='Class Weight')
plt.show()
"""

#%%

def build_model(hp):
    # start building model
    model = keras.Sequential()
    # input layer - five features
    model.add(keras.Input(shape=(5,), name="input_layer"))
    # add 1 to 3 hidden layers
    HL1 = hp.Int('units_1', min_value=1, max_value=32, step=1)
    HL2 = hp.Int('units_2', min_value=0, max_value=32, step=1)
    HL3 = hp.Int('units_3', min_value=0, max_value=32, step=1)
    
    model.add(
        keras.layers.Dense(
            units=HL1,
            activation=hp.Choice("activation", ["relu", "sigmoid", "tanh", "selu", "elu"])
            )
        )
    if HL2:
        model.add(
            keras.layers.Dense(
                units=HL2,
                activation=hp.Choice("activation", ["relu", "sigmoid", "tanh", "selu", "elu"])
                )
            )
        
    if HL3:
        model.add(
            keras.layers.Dense(
                units=HL3,
                activation=hp.Choice("activation", ["relu", "sigmoid", "tanh", "selu", "elu"])
                )
            )
    
    # output layer - 15 features
    model.add(keras.layers.Dense(units=15, activation=keras.activations.softmax))
    
    # tunable leanring rate
    learning_rate = hp.Float(
        "lr", min_value=1e-4, max_value=1e-1, sampling="log"
        )
    
    #Adam from convention
    model.compile(
        keras.optimizers.Adam(learning_rate=learning_rate),
        loss="CategoricalFocalCrossentropy",
        metrics=[keras.metrics.CategoricalAccuracy(name="categorical_accuracy", dtype=None)]
    )
    
    
    return model

"""
#Best Model
model = keras.Sequential()
model.add(keras.Input(shape=(5,), name="input_layer"))
model.add(keras.layers.Dense(units=27, activation=keras.activations.sigmoid))
model.add(keras.layers.Dense(units=31, activation=keras.activations.sigmoid))
model.add(keras.layers.Dense(units=27, activation=keras.activations.sigmoid))
model.add(keras.layers.Dense(units=15, activation=keras.activations.softmax))
model.compile(
    keras.optimizers.Adam(learning_rate=0.0046185576474882676),
    loss="CategoricalFocalCrossentropy",
    metrics=[keras.metrics.CategoricalAccuracy(name="categorical_accuracy", dtype=None)]
)
"""
#%%

#Early stopping
callback = keras.callbacks.EarlyStopping(
    monitor="val_loss",
    min_delta=0,
    patience=2,
    restore_best_weights=True,
    start_from_epoch=0,
)

epoch_length = 20 #10+
batch_size_length = 64 #16-256
val_split_length = 0.25 #From above

build_model(keras_tuner.HyperParameters())

tuner = keras_tuner.BayesianOptimization(
    hypermodel=build_model,
    objective="val_loss",
    max_trials=1,
    num_initial_points=50,
    alpha=0.0001,
    beta=2.6,
    seed=144,
    tune_new_entries=True,
    allow_new_entries=True,
    max_retries_per_trial=0,
    max_consecutive_failed_trials=3,
    overwrite=True
)

tuner.search(
    pheno_train,
    eco_train,
    epochs=epoch_length,
    validation_split=val_split_length,
    batch_size=batch_size_length,
    callbacks=[callback],
    shuffle=True,
    )

models = tuner.get_best_models(num_models=10)

best_model = models[0]
best_model.summary()
best_model = models[1]
best_model.summary()
best_model = models[2]
best_model.summary()

tuner.results_summary()
    
#%%

best_hps = tuner.get_best_hyperparameters(num_trials=1)
model = build_model(best_hps[0])
np.random.seed(144)
history = model.fit(
    x=pheno_train,
    y=eco_train,
    epochs=epoch_length,
    validation_split=val_split_length,
    batch_size=batch_size_length,
    callbacks=[callback],
    verbose='auto',
    shuffle=True,
    sample_weight=None,
    initial_epoch=0)

#%%

plt.plot(range(0,len(history.history['loss'])), history.history['loss'], c='k', label="loss")
plt.plot(range(0,len(history.history['val_loss'])), history.history['val_loss'], c='r', label="val loss")
plt.legend(loc='best')
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.show()

plt.plot(range(0,len(history.history['loss'])), history.history['categorical_accuracy'], c='k', label="categorical_accuracy")
plt.plot(range(0,len(history.history['val_loss'])), history.history['val_categorical_accuracy'], c='b', label="val_categorical_accuracy")
plt.legend(loc='best')
plt.xlabel("Epoch")
plt.ylabel("Accuracy")
plt.show()

#%%
from sklearn.metrics import confusion_matrix

#Predict
eco_pred = model.predict(pheno_test)

#Create confusion matrix and normalizes it over predicted (columns)
result = confusion_matrix(np.argmax(eco_test, axis=1), np.argmax(eco_pred, axis=1), normalize='pred')

ax = sns.heatmap(result, annot=False, fmt='g', vmin=0, vmax=1, yticklabels=frequency.keys(), xticklabels=frequency.keys())
ax.set(xlabel='Predicted', ylabel='True')
plt.show()

#%%

cmap = plt.get_cmap('turbo', 15)

# Predicted map
fig, ax = plt.subplots()
cax = ax.scatter(latlon_test.longitude, latlon_test.latitude, s = 0.0001, c=np.argmax(eco_pred, axis=1), cmap=cmap, vmin=0.5, vmax=15.5)
fig.colorbar(cax)
plt.show()
#0.001 for smoothest
#0.0001 for compromise


# True map
fig, ax = plt.subplots()
cax = ax.scatter(latlon_test.longitude, latlon_test.latitude, s = 0.0001, c=np.argmax(eco_test, axis=1), cmap=cmap, vmin=0.5, vmax=15.5)
fig.colorbar(cax)
plt.show()

#%%

cmap = plt.get_cmap('PiYG', 2)

acc_array = (eco_pred==eco_test)

# True/False map
fig, ax = plt.subplots()
cax = ax.scatter(latlon_test.longitude,
                 latlon_test.latitude,
                 s = 0.00001,
                 c= np.multiply([(np.argmax(eco_test, axis=1) - np.argmax(eco_pred, axis=1)) == 0], 1),
                 cmap=cmap,
                 vmin=0,
                 vmax=1
)
plt.show()

#%%
"""

def build_model(hp):
    # start building model
    model = keras.Sequential()
    # input layer stays the same as before
    model.add(keras.Input(shape=(5,), name="input_layer"))
    # instead of choosing the number of nodes, we add an hp object
    hp_units_1 = hp.Int('units_1', min_value=1, max_value=10, step=1)
    hp_units_2 = hp.Int('units_2', min_value=1, max_value=10, step=1)
    ##hp_units_3 = hp.Int('units_3', min_value=1, max_value=10, step=1)
    model.add(
        keras.layers.Dense(
            units=hp_units_1,
            activation=hp.Choice("activation", ["relu", "sigmoid", "tanh", "selu", "elu", "exponential"])
            )
        )
    model.add(
        keras.layers.Dense(
            units=hp_units_2,
            activation=hp.Choice("activation", ["relu", "sigmoid", "tanh", "selu", "elu", "exponential"])
            )
        )
    ##model.add(
        ##keras.layers.Dense(
            ##units=hp_units_3,
            ##activation=keras.activations.relu
            ##)
        ##)
    model.add(keras.layers.Dense(units=16, activation=keras.activations.softmax))
    # likewise, we will search for the learning rate
    learning_rate = hp.Float(
        "lr", min_value=1e-4, max_value=1e-1, sampling="log"
        )
    model.compile(
        keras.optimizers.SGD(learning_rate=learning_rate),
        loss='categorical_crossentropy',
        metrics=[keras.metrics.CategoricalAccuracy(name="categorical_accuracy", dtype=None)]
        )
    return model

build_model(keras_tuner.HyperParameters())

tuner = keras_tuner.BayesianOptimization(
    hypermodel=build_model,
    objective="val_loss",
    max_trials=100,
    num_initial_points=50,
    alpha=0.0001,
    beta=2.6,
    seed=144,
    tune_new_entries=True,
    allow_new_entries=True,
    max_retries_per_trial=0,
    max_consecutive_failed_trials=3,
    overwrite=True
)

tuner.search(
    pheno_train1,
    eco_train1,
    epochs=20,
    #batch_size=64,
    #batch_size=256,
    #batch_size=512,
    batch_size=1024,
    class_weight=cw,
    validation_data=(
        pheno_train2,
        eco_train2)
    )

models = tuner.get_best_models(num_models=3)

best_model = models[0]
best_model.summary()
best_model = models[1]
best_model.summary()
best_model = models[2]
best_model.summary()

tuner.results_summary()
"""