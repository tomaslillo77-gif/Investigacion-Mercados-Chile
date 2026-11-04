import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def create_professional_template(output_path: str = "data/portfolio_data.xlsx"):
    """Create a professional Excel template for client portfolio data"""
    Path("data").mkdir(exist_ok=True)

    wb = Workbook()

    # Remove default sheet and create our sheets
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])

    # Define styles
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Sheet 1: Advisors
    ws_advisors = wb.create_sheet("Advisors", 0)
    advisors_data = {
        'Advisor_ID': ['advisor_1', 'advisor_2', 'advisor_3', 'advisor_4', 'advisor_5', 'advisor_6'],
        'Name': ['Advisor Name 1', 'Advisor Name 2', 'Advisor Name 3', 'Advisor Name 4', 'Advisor Name 5', 'Advisor Name 6'],
        'Email': ['advisor1@company.com', 'advisor2@company.com', 'advisor3@company.com', 'advisor4@company.com', 'advisor5@company.com', 'advisor6@company.com'],
        'Phone': ['', '', '', '', '', ''],
    }

    df_advisors = pd.DataFrame(advisors_data)
    for r_idx, row in enumerate(df_advisors.values, 1):
        for c_idx, value in enumerate(row, 1):
            cell = ws_advisors.cell(row=r_idx, column=c_idx, value=value)
            if r_idx == 1:
                cell.fill = header_fill
                cell.font = header_font
            cell.border = border

    # Add headers
    for c_idx, header in enumerate(df_advisors.columns, 1):
        cell = ws_advisors.cell(row=1, column=c_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = center_align

    ws_advisors.column_dimensions['A'].width = 15
    ws_advisors.column_dimensions['B'].width = 20
    ws_advisors.column_dimensions['C'].width = 25
    ws_advisors.column_dimensions['D'].width = 15

    # Sheet 2: Clients
    ws_clients = wb.create_sheet("Clients", 1)
    clients_data = {
        'RUT': ['12345678-9', '87654321-0', '11223344-5', '22334455-6', '33445566-7'],
        'Name': ['Client Name A', 'Client Name B', 'Client Name C', 'Client Name D', 'Client Name E'],
        'Advisor_ID': ['advisor_1', 'advisor_1', 'advisor_2', 'advisor_2', 'advisor_3'],
        'Architecture': ['Balanced', 'Growth', 'Conservative', 'Balanced', 'Aggressive'],
        'Risk_Profile': ['Medium', 'High', 'Low', 'Medium', 'High'],
        'Portfolio_Type': ['Managed', 'Managed', 'Managed', 'Self-Directed', 'Managed'],
        'Portfolio_Value_USD': [500000, 750000, 1200000, 600000, 900000],
        'Target_Return_%': [5, 7, 2, 5, 8],
        'Benchmark': ['S&P 500', 'NASDAQ', 'Bloomberg Barclays', 'S&P 500', 'Russell 2000']
    }

    df_clients = pd.DataFrame(clients_data)

    # Add headers
    for c_idx, header in enumerate(df_clients.columns, 1):
        cell = ws_clients.cell(row=1, column=c_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = center_align

    # Add data
    for r_idx, row in enumerate(df_clients.values, 2):
        for c_idx, value in enumerate(row, 1):
            cell = ws_clients.cell(row=r_idx, column=c_idx, value=value)
            cell.border = border
            if c_idx == 7:  # Portfolio Value
                cell.number_format = '#,##0'
            elif c_idx == 8:  # Target Return
                cell.number_format = '0.00'

    ws_clients.column_dimensions['A'].width = 15
    ws_clients.column_dimensions['B'].width = 20
    ws_clients.column_dimensions['C'].width = 15
    ws_clients.column_dimensions['D'].width = 15
    ws_clients.column_dimensions['E'].width = 15
    ws_clients.column_dimensions['F'].width = 15
    ws_clients.column_dimensions['G'].width = 18
    ws_clients.column_dimensions['H'].width = 15
    ws_clients.column_dimensions['I'].width = 18

    # Sheet 3: Holdings
    ws_holdings = wb.create_sheet("Holdings", 2)
    holdings_data = {
        'Client_RUT': ['12345678-9', '12345678-9', '12345678-9', '12345678-9',
                       '87654321-0', '87654321-0', '87654321-0', '87654321-0'],
        'Asset_Class': ['Stocks', 'Bonds', 'Real Estate', 'Cash',
                        'Stocks', 'Bonds', 'Commodities', 'Cash'],
        'Position_Name': ['US Large Cap ETF', 'Corporate Bonds ETF', 'Real Estate Fund', 'Money Market',
                         'Tech Growth ETF', 'Government Bonds', 'Gold ETF', 'Cash Reserve'],
        'Ticker': ['VTI', 'LQD', 'VNQ', 'VMFXX',
                  'QQQ', 'IEF', 'GLD', 'CASH'],
        'Units': [1000, 5000, 500, 50000,
                 800, 3000, 300, 100000],
        'Unit_Price_USD': [250, 100, 40, 1,
                          320, 95, 190, 1],
        'Current_Value_USD': [250000, 500000, 20000, 50000,
                             256000, 285000, 57000, 100000],
        'Target_Allocation_%': [60, 25, 10, 5,
                               70, 20, 5, 5],
        'Current_Allocation_%': [50, 40, 10, 0,
                                 44, 39, 10, 7],
        'Last_Updated': ['2026-09-08', '2026-09-08', '2026-09-08', '2026-09-08',
                        '2026-09-08', '2026-09-08', '2026-09-08', '2026-09-08']
    }

    df_holdings = pd.DataFrame(holdings_data)

    # Add headers
    for c_idx, header in enumerate(df_holdings.columns, 1):
        cell = ws_holdings.cell(row=1, column=c_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = center_align

    # Add data
    for r_idx, row in enumerate(df_holdings.values, 2):
        for c_idx, value in enumerate(row, 1):
            cell = ws_holdings.cell(row=r_idx, column=c_idx, value=value)
            cell.border = border
            if c_idx in [5, 6, 7]:  # Units, Price, Value
                cell.number_format = '#,##0'
            elif c_idx in [8, 9]:  # Allocations
                cell.number_format = '0.00'

    for idx, header in enumerate(df_holdings.columns, 1):
        ws_holdings.column_dimensions[get_column_letter(idx)].width = 16

    # Sheet 4: Portfolio Architectures
    ws_arch = wb.create_sheet("Portfolio_Architectures", 3)
    architectures = []
    for arch in ['Conservative', 'Balanced', 'Growth', 'Aggressive']:
        for risk in ['Low', 'Low-Medium', 'Medium', 'Medium-High', 'High']:
            if arch == 'Conservative':
                stocks, bonds, real_estate, cash = 20+5, 60-5, 15, 5
            elif arch == 'Balanced':
                stocks, bonds, real_estate, cash = 50, 30, 15, 5
            elif arch == 'Growth':
                stocks, bonds, real_estate, cash = 70, 15, 10, 5
            else:  # Aggressive
                stocks, bonds, real_estate, cash = 85, 5, 8, 2

            architectures.append({
                'Architecture': arch,
                'Risk_Profile': risk,
                'Stocks_%': stocks,
                'Bonds_%': bonds,
                'Real_Estate_%': real_estate,
                'Cash_%': cash
            })

    df_arch = pd.DataFrame(architectures)

    # Add headers
    for c_idx, header in enumerate(df_arch.columns, 1):
        cell = ws_arch.cell(row=1, column=c_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = center_align

    # Add data
    for r_idx, row in enumerate(df_arch.values, 2):
        for c_idx, value in enumerate(row, 1):
            cell = ws_arch.cell(row=r_idx, column=c_idx, value=value)
            cell.border = border
            if c_idx >= 3:  # Allocation percentages
                cell.number_format = '0.00'

    for idx, header in enumerate(df_arch.columns, 1):
        ws_arch.column_dimensions[get_column_letter(idx)].width = 16

    # Sheet 5: Instructions
    ws_instructions = wb.create_sheet("README", 4)
    instructions = [
        ["PORTFOLIO DASHBOARD - DATA ENTRY INSTRUCTIONS"],
        [],
        ["SHEET 1: Advisors"],
        ["- Advisor_ID: Unique identifier (advisor_1, advisor_2, etc.)"],
        ["- Name: Full name of the investment advisor"],
        ["- Email: Advisor email address"],
        ["- Phone: Contact phone number"],
        [],
        ["SHEET 2: Clients"],
        ["- RUT: Client ID/RUT number"],
        ["- Name: Client name"],
        ["- Advisor_ID: Which advisor manages this client"],
        ["- Architecture: Conservative, Balanced, Growth, or Aggressive"],
        ["- Risk_Profile: Low, Low-Medium, Medium, Medium-High, High"],
        ["- Portfolio_Type: Managed (advisor-managed) or Self-Directed"],
        ["- Portfolio_Value_USD: Total portfolio value in USD"],
        ["- Target_Return_%: Expected annual return target"],
        ["- Benchmark: Benchmark index for comparison"],
        [],
        ["SHEET 3: Holdings"],
        ["- Client_RUT: RUT of the client owning this position"],
        ["- Asset_Class: Type of asset (Stocks, Bonds, Real Estate, Commodities, Cash)"],
        ["- Position_Name: Name of the specific position/fund"],
        ["- Ticker: Stock/fund ticker symbol"],
        ["- Units: Number of units held"],
        ["- Unit_Price_USD: Price per unit in USD"],
        ["- Current_Value_USD: Total value (Units × Price)"],
        ["- Target_Allocation_%: Desired % of portfolio"],
        ["- Current_Allocation_%: Actual % of portfolio"],
        ["- Last_Updated: Date of last update (YYYY-MM-DD)"],
        [],
        ["SHEET 4: Portfolio_Architectures"],
        ["- Do not edit this sheet - it defines the target allocations"],
        ["- It's automatically referenced by the dashboard"],
        [],
        ["HOW TO USE:"],
        ["1. Fill in your advisor details in the 'Advisors' sheet"],
        ["2. Add your clients in the 'Clients' sheet"],
        ["3. Add each client's holdings in the 'Holdings' sheet"],
        ["4. Save the file as 'portfolio_data.xlsx' in the 'data' folder"],
        ["5. Run: streamlit run app.py"],
    ]

    for row_idx, row_data in enumerate(instructions, 1):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws_instructions.cell(row=row_idx, column=col_idx, value=value)
            if row_idx == 1:
                cell.font = Font(bold=True, size=14)
            elif 'SHEET' in str(value) or 'HOW TO USE' in str(value):
                cell.font = Font(bold=True, size=11)
            cell.border = border

    ws_instructions.column_dimensions['A'].width = 80

    # Save workbook
    wb.save(output_path)
    print(f"✅ Professional template created at {output_path}")
    print("\n📝 Template includes:")
    print("   - Advisors sheet (6 advisors)")
    print("   - Clients sheet (5 sample clients)")
    print("   - Holdings sheet (8 sample positions)")
    print("   - Portfolio Architectures (4 × 5 = 20 profiles)")
    print("   - README sheet with instructions")


if __name__ == "__main__":
    create_professional_template()
