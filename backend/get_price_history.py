import yfinance as yf
from datetime import date, timedelta
# import pandas as pd
import os
os.environ["YFINANCE_IPV4"] = "True"

def write_to_file(data, filename="price_history.csv"):
    """
    Writes the given data to a CSV file.
    """
    data.to_csv(filename)
    print(f"Data written to {filename}")

def get_price_history(ticker_symbol, start_date, end_date):
    """
    Fetches historical price data for a given stock ticker symbol between specified dates.
    """
    # Download historical price data using yfinance
    stock_data = yf.download(ticker_symbol, start=start_date, end=end_date)
    
    # Print the fetched data
    print(stock_data)
    
    return stock_data
if __name__ == "__main__":
    data = get_price_history("AAPL", "2025-01-01", str(date.today()-timedelta(days=1))) # Fetch data up to yesterday
    write_to_file(data, "aapl_price_history_temp.csv")
    # print(date.today())