import requests
import os, sys
from datetime import datetime, timedelta
import pandas
import newsapi
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText


EMAIL = os.environ['EMAIL']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']
NEWS_API_KEY = os.environ['NEWS_API_KEY']
ALPHA_VANTAGE_API_KEY = os.environ['ALPHA_VANTAGE_API_KEY']
# You need to declare here which stocks you want to receive the reports
STOCKS = ["IBM", "TSLA", "AAPL", "GOOG", "MSFT", "AMZN", "META"]
PARAMETERS_ALPHA_VANTAGE = {
    'function': "TIME_SERIES_INTRADAY",
    'symbol':"",
    'interval': "60min",
    'apikey': ALPHA_VANTAGE_API_KEY,
}


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

# Taking data of each one of the companies and putting it on the "all_stocks" dict
for stocks in STOCKS:
    PARAMETERS_ALPHA_VANTAGE['symbol'] = stocks
    response = requests.get(url="https://www.alphavantage.co/query", params=PARAMETERS_ALPHA_VANTAGE)
    response.raise_for_status()
    data = response.json()
    all_stocks[stocks] = data

prices_dict = {}    # Definitive dict where the more "formated" data will go in
# Taking the specific data from each company and separating it into dicts inside the big "prices_dict" dict.
# You could separate other types of information here, depends on what you want. Pretty easy to change
for stocks in all_stocks:
    # For some reason, sometimes there is a KeyError on "Time Series (60min)". I don't know what it is, but I believe
    # it has something to do with the API json the program is receiving, but I'm not sure as the API is very pro.
    try:
        open_price = float(all_stocks[stocks]["Time Series (60min)"][f"{today_date} 05:00:00"]["1. open"])
        close_price = float(all_stocks[stocks]["Time Series (60min)"][f"{today_date} 20:00:00"]["4. close"])
        net_change = round(close_price - open_price, 4)
        percentage_diff = percentage_maker(net_change, open_price)
        prices_dict[stocks] = {
            'Opening price': "{:.2f}".format(open_price),  # Tried to make a nice formation, but the email csv
            'Closing price': "{:.2f}".format(close_price),  # ignores it anyway...
            'Net Change': "{:.2f}".format(net_change),
            'Percentage': percentage_diff,
        }
    except KeyError:
        # On days when the stock is not open, there will be no data to be collected, so no report
        # The KeyError will be mainly because when you use the "today" variable on the all_stocks dict, there
        # will be no key to the day "today" because it will be closed!
        # Plus: if there is a bug for some reason(the one mentioned above) the program will just skip the buggy
        # stocks. If every stock is buggy, then that's a big problem! But only testing it a lot to know if it will
        # really bug. From what I tested so far, it is only some totally random stocks that does not have the data
        print(f"Bug on {stocks}")
        pass
if not prices_dict:
    sys.exit()


# Making the csv file that will be sent through email
prices_data = pandas.DataFrame(prices_dict)
prices_data = prices_data.transpose()
prices_data.to_csv("prices_data.csv")

# Getting the news
# I thought a little confusing how this API works, so this part of my code is flawed. When I send the email, it
# sends some HTML stuff and I don't really know why. I will come back later to this code and remake the news part,
# get more news (three is a good number, if available) and get rid of this bug.
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
# I first learned how to send emails using with ... as ..., so it felt more natural to use it
# I don't know if handling the connection before setting up the email is bad practice
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
