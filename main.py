import os.path
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from fastapi import FastAPI
from mangum import Mangum
import pandas as pd

app = FastAPI()
handler = Mangum(app)


@app.get("/")
async def root():
    response = {
        "message": "stockSense API backend",
        "version_info": "2023.8.17.1"
    }
    return response


@app.get("/query/{symbol}")
async def query(symbol: str):
    try:
        stock = symbol.split(".", 1)[0]
        df = pd.read_csv('equity_bse.csv')
        result = df.loc[df["SYMBOL"] == stock, "STOCK"]
        stock_name= result.values[0]
    except:
        stock_name= symbol

    data = yf.download(symbol, interval='1d')
    JSONresponse = {
        "stock_name": stock_name,
        "t1": data['Close'].iloc[-2],
        "t2": data['Close'].iloc[-3],
        "t3": data['Close'].iloc[-4],
        "t4": data['Close'].iloc[-5],
        "t5": data['Close'].iloc[-6],
        "t6": data['Close'].iloc[-7]
    }
    return JSONresponse


@app.get("/info/{symbol}")
async def info(symbol: str):
    ticker = yf.Ticker(symbol)
    stock_info = ticker.info
    stock_name = stock_info.get('longName')
    quote_type = stock_info.get('quoteType')

    JSON = {
        "symbol": symbol,
        "stock_name": stock_name,
        "quote_type": quote_type
    }

    return JSON


@app.get("/ltp/{symbol}")
async def ltp(symbol):
    data = yf.download(symbol, interval='1m', period='1d')
    ltp = (data['Close'].iloc[-1])
    previous_close = yf.download(symbol, interval='1d')['Close'].iloc[-1]
    response = {
        "ltp": round(ltp, 2),
        "change": changePositiveNegative(ltp=ltp, previous_close=previous_close)
    }
    return response

@app.get("/technical/{symbol}")
async def technicals(symbol):
    stock = symbol.split(".", 1)[0]
    df = pd.read_csv('equity_bse.csv')
    result = df.loc[df["SYMBOL"] == stock, ["FaceValue", "ISIN", "IndustryNew"]]
    print(result)

    data= yf.download(symbol, period="1y")
    sma50= data['Close'].rolling(window=50).mean().iloc[-1]
    ema50= data['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    sma100 = data['Close'].rolling(window=100).mean().iloc[-1]
    ema100 = data['Close'].ewm(span=100, adjust=False).mean().iloc[-1]
    sma200 = data['Close'].rolling(window=200).mean().iloc[-1]
    ema200 = data['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
    rsi= 100 - (100 / (1 + (data['Close'].diff(1).fillna(0) > 0).rolling(window=14).mean())).iloc[-1]
    macd = data['Close'].ewm(span=12, adjust=False).mean() - data['Close'].ewm(span=26, adjust=False).mean()
    bollingerBandUpper= data['Close'].rolling(window=20).mean() + 2 * data['Close'].rolling(window=20).std()
    bollingerBandLower = data['Close'].rolling(window=20).mean() - 2 * data['Close'].rolling(window=20).std()
    atr= data['High'].rolling(window=14).max() - data['Low'].rolling(window=14).min()

    response= {
        "faceValue": result["FaceValue"].values[0],
        "ISIN": result["ISIN"].values[0],
        "industry": result["IndustryNew"].values[0],
        "sma50": sma50,
        "ema50": ema50,
        "sma100": sma100,
        "ema100": ema100,
        "sma200": sma200,
        "ema200": ema200,
        "rsi": rsi,
        "macd": macd.iloc[-1],
        "bollingerBandUpper": bollingerBandUpper.iloc[-1],
        "bollingerBankLoweer": bollingerBandLower.iloc[-1],
        "atr": atr.iloc[-1]
    }

    return response


@app.get("/prediction/{symbol}")
async def prediction(symbol: str):
    end_date = '2023-01-20'
    df = yf.download(symbol, period='max', end=end_date)
    df = df.reset_index()
    trainSet = df.iloc[:, 1:2].values
    scaler = MinMaxScaler(feature_range=(0, 1))
    trainingSetScaled = scaler.fit_transform(df['Close'].values.reshape(-1, 1))

    testDF = yf.download(symbol, period='max', start=end_date, end=datetime.now())
    realSP = testDF['Close'].values
    dfTotal = pd.concat((df['Open'], testDF['Open']), axis=0)
    modelInp = dfTotal[len(dfTotal) - len(testDF) - 60:].values
    modelInp = modelInp.reshape(-1, 1)
    modelInp = scaler.transform(modelInp)
    realData = [modelInp[len(modelInp) - 60:len(modelInp + 1), 0]]
    realData = np.array(realData)
    realData = np.reshape(realData, newshape=(realData.shape[0], realData.shape[1], 1))
    predic = predictionFunction(symbol, realData)
    prediction_scaled = scaler.inverse_transform(predic)
    jsonData = {
        "predicted_close": float(prediction_scaled[0][0])
    }
    return jsonData


def predictionFunction(symbol, realData):
    interpreter = tf.lite.Interpreter(
        model_path=os.path.join('exports', f'{symbol}.tflite'))
    interpreter.allocate_tensors()

    # Get input and output details from the model
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # Prepare input data
    input_shape = input_details[0]['shape']
    input_data = np.array(realData, dtype=np.float32)

    # Set the input tensor and run the inference
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()

    # Get the output tensor and process the predictions
    output_data = interpreter.get_tensor(output_details[0]['index'])
    predictions = output_data
    return predictions


def changePositiveNegative(ltp, previous_close):
    change = (ltp - previous_close)
    print(change)
    print(previous_close)
    if (change > 0):
        return "POSITIVE"
    elif (change < 0):
        return "NEGATIVE"
    else:
        return "NEUTRAL"
