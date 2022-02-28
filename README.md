# Stock Sentiment Analysis

This project analyzes the posts and comments from the daily discussion thread of the "WallStreetBets" subreddit.

The natural language processing model used is a VADER (Valence Aware Dictionary for Sentiment Reasoning), a parsimonious rule-based model. 
The VADER model was used because of how well it performs on short social media text but can
generalize to multiple domains of language. This makes it ideal for analyzing a subreddit and generalizing our domain of finance.

The final sentiment score for each stock was very volatile on day-to-day basis and
was not of much use in its raw form. After Fourier transforms with a sampling rate of
every 20, and 5 days, the signal became much smoother and proved to show some
correlation with the stock price. However, it was not enough to provide a confident "buy" or "sell" signal. 
From the histroical data we could tell the sentiment score would always lag behind the actually price of the stock.
