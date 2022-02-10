
import os
import json
import time
import datetime
import requests
import numpy as np
import pandas as pd
import seaborn as sn
import matplotlib.pyplot as plt
import praw  # reddit data api
import ffn  # for loading financial data
import numerapi  # for numerai tickers
import argparse

# VADER sentiment model
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from tqdm.auto import tqdm
from sklearn.preprocessing import MinMaxScaler

# Commented out IPython magic to ensure Python compatibility.

parser = argparse.ArgumentParser()
parser.add_argument('--startDate', metavar='-s', type=str, help="Start date from when to start capturing", required=True)
parser.add_argument('--endDate', metavar='-e', type=str, help="End date from when to end capturing", required=True)
parser.add_argument('--ticker', metavar='-t', type=str, help="Single ticker to find sentiment value for")
parser.add_argument('--tickers', metavar='-ts', nargs='+', help="List of multiple tickers")
args = parser.parse_args()

start_date = args.startDate
end_date = args.endDate

to_date = str(int(time.mktime(datetime.datetime.strptime(end_date, "%d/%m/%Y").timetuple())))
from_date = str(int(time.mktime(datetime.datetime.strptime(start_date, "%d/%m/%Y").timetuple())))

subReddit = 'wallstreetbets'

numerAI = numerapi.SignalsAPI()
eligible_tickers = pd.Series(
    numerAI.ticker_universe(), name="bloomberg_ticker")
numerAI_ticker_map = pd.read_csv(
    'https://numerai-signals-public-data.s3-us-west-2.amazonaws.com/signals_ticker_map_w_bbg.csv')
bb_tickers = numerAI_ticker_map["bloomberg_ticker"]

def get_subreddit_data(subm):
    subData = [subm['id'], subm['title'], subm['url'],
               datetime.datetime.fromtimestamp(subm['created_utc']).date()]
    try:
        flair = subm['link_flair_text']
    except KeyError:
        flair = "NaN"
    subData.append(flair)
    subStats.append(subData)

def get_Pushshift_Data(query, after, before, sub):
    reURL = 'https://api.pushshift.io/reddit/search/submission/?title=' + \
        str(query)+'&size=1000&after='+str(after) + \
        '&before='+str(before)+'&subreddit='+str(sub)
    print(reURL)
    r = requests.get(reURL)
    data = json.loads(r.text)
    return data['data']

# Subreddit information
channel = "Daily Discussion"
query = "Daily Discussion"
subCount = 0
subStats = []

# Organize into a dataframe

reddit_ids = []
subreddit_titles = []
urls = []
dates = []
flairs = []

daily_comments = []
ticks_ = []

sentiment_scores = []  # For entire market
daily_sentiments = []  # array of dictionaries with daily ticker sentiments

# Get all the data from pushshift and parse it below
response_body_data = get_Pushshift_Data(query, from_date, to_date, subReddit)
while len(response_body_data) > 0:
    for submission in response_body_data:
        get_subreddit_data(submission)
        subCount += 1
    print(len(response_body_data))
    print(str(datetime.datetime.fromtimestamp(
        response_body_data[-1]['created_utc'])))
    from_date = response_body_data[-1]['created_utc']
    try:
        response_body_data = get_Pushshift_Data(query, from_date, to_date, subReddit)
    except Exception as e:
        print(e)

response_body_data = {}
for stat in subStats:
    reddit_ids.append(stat[0])
    subreddit_titles.append(stat[1])
    urls.append(stat[2])
    dates.append(stat[3])
    flairs.append(stat[4])
response_body_data['id'] = reddit_ids
response_body_data['title'] = subreddit_titles
response_body_data['url'] = urls
response_body_data['date'] = dates
response_body_data['flair'] = flairs
dataFrame_1 = pd.DataFrame(response_body_data)
dataFrame_1 = dataFrame_1[(dataFrame_1['flair'] == channel)]

# Download data from Reddit
reddit = praw.Reddit(client_id='1XambE_tem5SOw',
                     client_secret='F5ihhavbKJQ_-E5aLMw5OgAZ-bAz4w',
                     user_agent='Requests')

for url in tqdm(dataFrame_1['url'].tolist()):
    try:
        submission = reddit.submission(url=url)
        submission.comments.replace_more(limit=0)
        comments = list([(comment.body) for comment in submission.comments])
    except:
        comments = None
    daily_comments.append(comments)

# Symbol filtering
# Removing comment English names that could also be guessed as ticker name
stopwords_list_file = open("ticker_stop_words.csv", "r")
try:
    file_data = stopwords_list_file.read()
    stop_words = file_data.split(",")
finally:
    stopwords_list_file.close()

stop_words += ['ATH', 'US', 'LOVE', 'ME', 'GET', 'PUMP', 'KIDS', 'TRUE', 'EDIT', 'DIE', 'WORK', 'MF']

filter_less = bb_tickers
filter_less = filter_less.apply(lambda x: x.split(" ")[0])
less_than_two_ticks = filter_less[filter_less.str.len() >= 2].values

less_than_two_ticks = [t for t in less_than_two_ticks if not str.isdigit(t)]
less_than_two_ticks = [t for t in less_than_two_ticks if t not in stop_words]

# Filter out based on the stop words we used earlier
for tic in less_than_two_ticks:
    if tic.lower() not in stop_words:
        ticks_.append(tic)

less_than_two_ticks = ticks_

np.intersect1d(less_than_two_ticks, [s.upper() for s in stop_words])

# Give a score to all comments to get sentiment
# Keep all tickers mentioned
# give the tickers involed Sentiment score

# Analysis USING VADER
analyser = SentimentIntensityAnalyzer()
for comments in tqdm(daily_comments):
    sent_ticks = dict()
    sentiment_score = 0
    for currTick in less_than_two_ticks:
        sent_ticks[currTick] = 0
    try:
        for comment in comments:
            ticks_in_comment = []
            for currTick in less_than_two_ticks:
                # Check if current comment contains any of the tickers
                if (" " + currTick + " " in comment) and (currTick.lower() not in stop_words):
                    ticks_in_comment.append(currTick)
            # Get a sentiment score for this comment
            comment_score = analyser.polarity_scores(comment)["compound"]

            # Update the score
            for currTick in ticks_in_comment:
                sent_ticks[currTick] = comment_score + sent_ticks[currTick]

            sentiment_score = sentiment_score + comment_score
        daily_sentiments.append(sent_ticks)
    except TypeError:
        sentiment_score = 0

    sentiment_scores.append(sentiment_score)

dataFrame_1["sentiment score"] = sentiment_scores

daily_arr = []
for day in daily_sentiments:
    daily_arr.append(pd.Series(day))

daily_dataframe = pd.concat(daily_arr, 1)
values_ = dataFrame_1.date.values[:len(dataFrame_1.date.values)]
daily_dataframe.columns = values_

up_top = daily_dataframe.sum(1).nlargest(200).index
down_top = daily_dataframe.sum(1).nsmallest(200).index
tickers = down_top.append(up_top)

"""1. Transpose, 
2. calculate rolling average
3. Transpose
"""
# Sum all days
sum_days = daily_dataframe[daily_dataframe.columns[:]].T.rolling(window=14).sum().T
sum_days = sum_days.iloc[:, -1]
sum_days = sum_days.loc[tickers]

sentiment_scores = sum_days.rank(pct=True).sort_values(ascending=False).reset_index()
sentiment_scores.columns = ["bloomberg_ticker", "signal"]

"""map shortned symbols back to bloomberg symbols"""
mapping = pd.Series(bb_tickers.values, index=bb_tickers.apply(
    lambda x: x.split(" ")[0]))
sentiment_scores["bloomberg_ticker"] = sentiment_scores["bloomberg_ticker"].apply(
    lambda x: mapping[x] if type(mapping[x]) == str else mapping[x].values[0])
sentiment_scores.set_index("bloomberg_ticker").to_csv(
    "Signal_WSB_ema.csv", index=True)


def plot_fft(cDataFrame, ticker_symbol):
    # We get the values from the ticker at an earlier start date
    target_ticker = ffn.get(ticker_symbol, start='2010-01-01')
    target_ticker_values = []

    # Get all values since that start date
    for date in tqdm(cDataFrame['date'].astype(str).values):
        try:
            target_ticker_values.append(float(target_ticker.loc[date]))
        except KeyError:
            target_ticker_values.append(None)

    cDataFrame[ticker_symbol] = target_ticker_values
    cDataFrame = cDataFrame[['date', 'sentiment score', ticker_symbol]]
    cDataFrame = cDataFrame.set_index('date')
    cDataFrame = cDataFrame[cDataFrame[ticker_symbol].notna()]

    cDataFrame.plot(secondary_y='sentiment score', figsize=(16, 10))

    # Apply Fourier Transoframtions to summarize our results
    close_fft = np.fft.fft(np.asarray(cDataFrame['sentiment score'].tolist()))
    fft_df = pd.DataFrame({'fft': close_fft})
    fft_df['absolute'] = fft_df['fft'].apply(lambda x: np.abs(x))
    fft_df['angle'] = fft_df['fft'].apply(lambda x: np.angle(x))
    fft_list = np.asarray(fft_df['fft'].tolist())
    fft_list_m10 = np.copy(fft_list)
    fft_list_m10[5:-5] = 0
    cDataFrame['fourier 5'] = np.fft.ifft(fft_list_m10)
    #cDataFrame[['sentiment score', 'fourier 5']].plot(figsize=(16, 10))

    # Normalize our Forier transforamtions.
    sc = MinMaxScaler(feature_range=(0, 1))
    cDataFrame['norm_price'] = sc.fit_transform(
        cDataFrame[ticker_symbol].to_numpy().reshape(-1, 1))
    cDataFrame[ticker_symbol + ' log'] = np.log(
        cDataFrame[ticker_symbol]/cDataFrame[ticker_symbol].shift(1))
    cDataFrame['norm_sentiment'] = sc.fit_transform(
        cDataFrame['sentiment score'].to_numpy().reshape(-1, 1))
    cDataFrame['norm_fourier5'] = sc.fit_transform(np.asarray(
        list([(float(x)) for x in cDataFrame['fourier 5'].to_numpy()])).reshape(-1, 1))
    cDataFrame[['norm_price', 'norm_sentiment',
                'norm_fourier5']].plot(figsize=(16, 10))

    # Generate a PDF of our current chart of sentiments
    import datetime
    filename = datetime.datetime.now().strftime("%Y %m %d %H %M %S")
    plt.title(start_date + " to "+end_date, fontsize=15)
    plt.suptitle(ticker_symbol.upper() + ' Sentiment Analysis', fontsize=29)
    plt.savefig(ticker_symbol.upper() + "_" + start_date.replace('/',
                '-') + "_" + end_date.replace('/', '-')+'_'+filename+'.pdf')


# Temporary until we have argparse setup
# ticker_symbols = ['spy', 'tsla', 'shop']
ticker_symbols = args.tickers
ticker_symbol = args.ticker
original_df_1 = dataFrame_1
if ticker_symbol == None:
    for ticker in ticker_symbols:
        plot_fft(original_df_1, ticker)
else:
    plot_fft(original_df_1, ticker_symbol)


#plot_fft(original_df_1, ticker)
# Clean out the data we have from bloomberg
os.remove('Signal_WSB_ema.csv')
print()