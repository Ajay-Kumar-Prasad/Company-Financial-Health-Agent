# test_api.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()


API_KEY = os.getenv("FMP_API_KEY")
symbol = "AAPL"

url = f"https://financialmodelingprep.com/stable/income-statement?symbol={symbol}&apikey={API_KEY}"

res = requests.get(url)
data = res.json()

if isinstance(data, list) and len(data) > 0:
    record = data[0]
    
    print("Revenue:", record.get("revenue"))
    print("Net Income:", record.get("netIncome"))
    print("Operating Income:", record.get("operatingIncome"))
else:
    print("API Error:", data)