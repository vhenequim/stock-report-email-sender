import requests
import os, sys
from datetime import datetime, timedelta
import pandas as pd
import newsapi
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
import matplotlib as plt


EMAIL = os.environ['EMAIL']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']
NEWS_API_KEY = os.environ['NEWS_API_KEY']
POLYGON_API_KEY  = os.environ['POLYGON_API_KEY ']

# You need to declare here which stocks you want to receive the reports
STOCKS = ["IBM", "TSLA", "META"]


def percentage_maker(difference, opening_price):       # Function to make the percentage a string ex: 38,84%
    raw_percentage = round(100*difference / opening_price, 2)
    return f"{raw_percentage}%"


def yesterday(frmt='%Y-%m-%d', string=True):   # Function to define yesterday date, not >really< used, but I
    yesterday = datetime.now() - timedelta(1)  # used it to test the code
    if string:
        return yesterday.strftime(frmt)
    return yesterday


all_stocks = {}         # Declared a dict to squeeze in all the API info inside it
today_date = datetime.today().strftime('%Y-%m-%d')
yesterday_date = yesterday()
from_date = "2023-01-09" 
to_date = "2023-01-09"  


for stocks in STOCKS:
    response = requests.get(url=f"https://api.polygon.io/v2/aggs/ticker/{stocks}"
                            "/range/1/hour/2023-01-09/2023-01-09?adjusted=true&sort=asc&limit=120&"
                            "apiKey=J7zN6s3CTwQ5k44V9TuRVUQoT66HfwJi")
    response.raise_for_status()
    data = response.json()
    all_stocks[stocks] = data

prices_dict = {}    # Definitive dict where the more "formated" data will go in
for ticker, stock_data in all_stocks.items():
    try:
        open_price = float(stock_data["results"][0]["o"])
        close_price = float(stock_data["results"][0]["c"])
        lowest_price = float(stock_data["results"][0]["l"])
        highest_price = float(stock_data["results"][0]["h"])
        number_of_trans = float(stock_data["results"][0]["n"])
        net_change = round(close_price - open_price, 4)
        percentage_diff = percentage_maker(net_change, open_price)
        prices_dict[ticker] = {
            'Opening price': "{:.2f}".format(open_price),  
            'Closing price': "{:.2f}".format(close_price),  
            'Net Change': "{:.2f}".format(net_change),
            'Highest price': "{:.2f}".format(highest_price),
            'Lowest price': "{:.2f}".format(lowest_price),
            'Number of Transactions': "{:.2f}".format(number_of_trans)
        }
    except KeyError:
        print(f"Bug on {ticker}")
        pass
if not prices_dict:
    sys.exit()

# Making the csv file that will be sent through email
prices_df = pd.DataFrame(prices_dict).transpose()
prices_df.to_csv("prices_data.csv")

news_dict = {}
newsapi = newsapi.NewsApiClient(api_key=NEWS_API_KEY)
for stocks in STOCKS:    # Here I used the same reasoning I used on other parts of the code
    try:
        top_headlines = newsapi.get_top_headlines(
            q=stocks, 
            category='business', 
            language='en',
        )
        news_dict[stocks] = {
            'Title': top_headlines['articles'][0]['title'],
            'Description': top_headlines['articles'][0]['description'],
            'URL': top_headlines['articles'][0]['url'],
        }
    except IndexError:
        news_dict[stocks] = "None"  # If there is no news on the topic 'business', there will be an IndexError

# Formatting the news to send into the email

news_email = ""
for stocks in news_dict:
    if news_dict[stocks] != "None":  # Making a chunk of news.
        temporary_string = f"\n{stocks}:" \
                           f"\n{news_dict[stocks]['Title']}" \
                           f"\n{news_dict[stocks]['Description']}\n" \
                           f"{news_dict[stocks]['URL']}\n"
        news_email += temporary_string
    else:
        temporary_string = f"\n{stocks}: There's no relevant news today.\n"
        news_email += temporary_string

# Sending emails
msg_body = f"Good Night! Here is your daily stocks report! Annexed is the csv with the Stocks net values changes\nNews section:{news_email}"
with smtplib.SMTP("smtp.gmail.com") as connection:
    connection.starttls()
    connection.login(EMAIL, EMAIL_PASSWORD)
    email_msg = MIMEMultipart()
    email_msg['Subject'] = f"Stocks review from {today_date}"
    email_body = MIMEText(msg_body, 'plain')
    email_msg.attach(email_body)
    with open("prices_data.csv", 'rb') as file: # File is supposed to be on the main directory, so no issues here
        email_msg.attach(MIMEApplication(file.read(), Name="prices_data.csv"))
    connection.sendmail(EMAIL, EMAIL, email_msg.as_string())



