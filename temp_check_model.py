from keras.models import load_model

model = load_model('stock_dl_model.h5')
model.summary()
