from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from typing import List, Dict
import os

app = FastAPI(title="Portfolio Dashboard API", version="0.1.0")

# Enable CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Portfolio Dashboard API"}


@app.get("/advisors")
def get_advisors():
    """Get list of all investment advisors"""
    return {
        "advisors": [
            "advisor_1",
            "advisor_2",
            "advisor_3",
            "advisor_4",
            "advisor_5",
            "advisor_6"
        ]
    }


@app.get("/advisor/{advisor_id}/clients")
def get_advisor_clients(advisor_id: str):
    """Get all clients for a specific advisor"""
    # This would eventually read from Excel file
    return {
        "advisor": advisor_id,
        "clients": [
            {
                "name": "Cliente A",
                "rut": "12345678-9",
                "portfolio_value": 500000,
                "risk_profile": "Moderate"
            },
            {
                "name": "Cliente B",
                "rut": "87654321-0",
                "portfolio_value": 750000,
                "risk_profile": "Aggressive"
            }
        ]
    }


@app.get("/client/{client_rut}/portfolio")
def get_client_portfolio(client_rut: str):
    """Get detailed portfolio for a specific client"""
    return {
        "rut": client_rut,
        "name": "Cliente A",
        "portfolio": [
            {
                "asset_class": "Stocks",
                "desired_allocation": 60,
                "actual_allocation": 65,
                "desired_value": 300000,
                "actual_value": 325000
            },
            {
                "asset_class": "Bonds",
                "desired_allocation": 25,
                "actual_allocation": 20,
                "desired_value": 125000,
                "actual_value": 100000
            }
        ],
        "rebalance_needed": True
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
