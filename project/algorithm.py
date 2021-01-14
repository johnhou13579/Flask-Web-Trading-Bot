from tda import auth, client
from os import path, environ
import json, datetime, pandas as pd, tda, time
from dateutil import parser
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from flask import Flask, jsonify, request, Blueprint, render_template, current_app as app
from flask_login import login_required, current_user
from . import db
from .models import User


algo = Blueprint('algo', __name__)

token = environ.get('token')
api_key = environ.get('api_key')
redirect_uri = environ.get('redirect_uri')

basedir = path.abspath(path.dirname(__file__))

'''
localStorage.setItem('token', 'example token');
console.log(localStorage.getItem('token'));
'''

@algo.route('/algo', methods=['GET','POST'])
@login_required
def display():
    try:
        c = auth.client_from_token_file(path.join(basedir, 'token'), api_key)
    except FileNotFoundError:
            from selenium import webdriver
            with webdriver.Chrome(executable_path=path.join(basedir, 'chromedriver')) as driver:
                c = auth.client_from_login_flow(
                    driver, api_key, redirect_uri, token)
    
    weightList, stockTicker = scores(c, str(request.form.get("list")))
    holdings = positions(c)
    if request.method == 'POST':
        return render_template('recalculate.html',  name=current_user.name, weightList=weightList, stockTicker = stockTicker, holdings = holdings)
    else:
        return render_template('algo.html',  name=current_user.name, weightList=weightList, stockTicker = stockTicker, holdings = holdings)

@algo.route('/orders')
@login_required
def orders():
    try:
        c = auth.client_from_token_file(path.join(basedir, 'token'), api_key)
    except FileNotFoundError:
            from selenium import webdriver
            with webdriver.Chrome(executable_path=path.join(basedir, 'chromedriver')) as driver:
                c = auth.client_from_login_flow(
                    driver, api_key, redirect_uri, token)
    orderList = ordersHelper(c)
    return render_template('orders.html', orderList = orderList)

@algo.route('/purchase', methods=['POST'])
@login_required
def purchase():
    try:
        c = auth.client_from_token_file(path.join(basedir, 'token'), api_key)
    except FileNotFoundError:
            from selenium import webdriver
            with webdriver.Chrome(executable_path=path.join(basedir, 'chromedriver')) as driver:
                c = auth.client_from_login_flow(
                    driver, api_key, redirect_uri, token)
    

    maxValue = request.form.get('stock')
    number_of_shares = request.form.get('quantity')

    acct = c.get_accounts()
    acct_id = str(acct.json()[0]['securitiesAccount']['accountId'])
    builder = tda.orders.EquityOrderBuilder(maxValue, number_of_shares)
    builder.set_instruction(builder.Instruction.BUY)
    builder.set_order_type(builder.OrderType.MARKET)
    builder.set_duration(tda.orders.Duration.DAY)
    builder.set_session(tda.orders.Session.NORMAL)
    order = builder.build()
    
    #r = c.place_order(acct_id, order)
    #assert r.ok, r.raise_for_status()
    
    return json.dumps({'order':order, 'success':True, 'method': "Buying.", 'maxValue': maxValue, "number_of_shares": number_of_shares}), 200, {'ContentType':'application/json'} 


@algo.route('/sell', methods=['POST'])
@login_required
def sell():
    try:
        c = auth.client_from_token_file(token, api_key)
    except FileNotFoundError:
            from selenium import webdriver
            with webdriver.Chrome(executable_path=path.join(basedir, 'chromedriver')) as driver:
                c = auth.client_from_login_flow(
                    driver, api_key, redirect_uri, token)
    
    maxValue = request.form.get('stock2')
    number_of_shares = request.form.get('quantity2')

    acct = c.get_accounts()
    acct_id = str(acct.json()[0]['securitiesAccount']['accountId'])
    builder = tda.orders.EquityOrderBuilder(maxValue, number_of_shares)
    builder.set_instruction(builder.Instruction.SELL)
    builder.set_order_type(builder.OrderType.MARKET)
    builder.set_duration(tda.orders.Duration.DAY)
    builder.set_session(tda.orders.Session.NORMAL)
    order = builder.build()
    
    #r = c.place_order(acct_id, order)
    #assert r.ok, r.raise_for_status()
    
    return json.dumps({'order':order, 'success':True, 'method': "Selling.", 'maxValue': maxValue, "number_of_shares": number_of_shares}), 200, {'ContentType':'application/json'} 



def scores(c, t = "None"):
    
    #Set hedge variables
    hedge = "AAPL"
    
    user = User.query.filter_by(email=current_user.email).first()

    if user.watchList != None and t == "None":
        etfs = user.watchList.split()
    elif t != "None":
        user.watchList = t
        etfs = t.split()
        db.session.commit()
    else:
        etfs = [
            "SPXL", # Daily S&P 500 Bull 3X Shares
            "AMZN", # Amazon
            "TSLA", # Tesla
            "AAPL", # Apple
            "AMD",  # AMD
            "PLTR",
            "ICLN",
            "ARKK",
            "ARKG"
    ]
    

    etfs.sort()
    state = 1
    highestPortfolio = 0
    target_leverage = 1
    
    #Set array for scores
    weightList = {}

    for i in etfs:
        #Get price history for each stock above
        his = c.get_price_history(i,
            period_type=client.Client.PriceHistory.PeriodType.YEAR,
            period=client.Client.PriceHistory.Period.ONE_YEAR,
            frequency_type=client.Client.PriceHistory.FrequencyType.DAILY,
            frequency=client.Client.PriceHistory.Frequency.DAILY)
        
        #Calculate scores and update weightList
        data = pd.read_json(json.dumps(his.json()['candles'], indent=4))
        one = (pd.DataFrame(data).tail(1).head(1)['close']).values[0]
        twentyone = (pd.DataFrame(data).tail(21).head(1)['close']).values[0]
        sixtythree = (pd.DataFrame(data).tail(63).head(1)['close']).values[0]
        onetwentysix = (pd.DataFrame(data).tail(126).head(1)['close']).values[0]
        weightList.update({i: one/twentyone*.43 + one/sixtythree * .33 + one/onetwentysix * .24 })

        assert his.ok, his.raise_for_status()

    #Get maxValue of scores and print maxValue with score
    maxValue = max(weightList, key=weightList.get)
    
    #If maxValue of scores are less than 0 then set to hedge
    if max(weightList.values())<=0:
        maxValue = hedge
    
    weightList = dict(sorted(weightList.items(), key=lambda x: x[1], reverse = True))    
    
    #buyStock(maxValue, target_leverage)

    idx = 1
    for name in weightList:
        weightList.update({name: [weightList[name], idx]})
        idx = idx+1

    return [weightList, maxValue]

def positions(c):
    curr_positions = c.get_accounts(fields=[c.Account.Fields.POSITIONS])
    
    instrument = {}
    temp = curr_positions.json()[0]['securitiesAccount']
    if "positions" in temp:
        instruments = json.loads(json.dumps(curr_positions.json()[0]['securitiesAccount']['positions']))
        for e in instruments:
            instrument[e["instrument"]["symbol"]] = [ int(e["longQuantity"]),"${:0.2f}".format(e["averagePrice"]), "${:0.2f}".format(e["marketValue"]/(e["longQuantity"]),2), "${:0.2f}".format(e["averagePrice"]*e["longQuantity"]), "$"+str(e["marketValue"]), "${:0.2f}".format(e["marketValue"]-(e["averagePrice"]*e["longQuantity"]),2), "{:0.2f}%".format((e["marketValue"]-(e["averagePrice"]*e["longQuantity"]))/(e["averagePrice"]*e["longQuantity"])*100,2)]

    return instrument

def ordersHelper(c):
    acct = c.get_accounts()
    id = str(acct.json()[0]['securitiesAccount']['accountId'])
    totalList =  json.loads(json.dumps(c.get_transactions(id, start_date=datetime.datetime.now() - relativedelta(months=+1), end_date=datetime.datetime.now()).json()))
    tradeList = []
    for i in totalList:
        if i["type"] == "TRADE":
            d = parser.parse(i['transactionDate'])
            #REFORMAT FOR READBILITY
            tradeList.append([str(i["transactionItem"]["instrument"]["symbol"]), str(i["transactionItem"]["instruction"]), str(i["transactionItem"]["amount"]), str(i["transactionItem"]["price"]), str(i["transactionItem"]["cost"]), d])
    return tradeList
""" 

Selling point is actually having it trade for you 
this includes by priority order
1. actually connecting to API and buying/selling
2. algorithm choosing something to buy 
3. using your own tda account + changing algorithms in list
4. changing time intervals
5. view trades/portfolio
6. changing brokerages/connecting accounts/api
7. viewing plots/charts

"""