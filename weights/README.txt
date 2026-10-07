BLOOMBERG INDEX WEIGHTS  (optional, makes the Top movers exact)

Without these files the Top movers use approximate weights (Yahoo market caps). With them, each stock is ranked by its
exact contribution to the index move: index weight (%) x day move (%).

HOW TO EXPORT ONE (about 1 minute per index, about once a month is plenty)
1. In Bloomberg type the index ticker, press <Equity>, then type  MEMB <GO>  (members). Examples:
      SPX Index MEMB    NDX Index MEMB    HSCEI Index MEMB    SHSZ300 Index MEMB    TWSE Index MEMB    KOSPI Index MEMB
2. Make sure the table shows the columns:  Ticker, Name and  % Weight  (use the "Index weight" / "% Wgt" column, not "Shares").
3. Sort by weight, largest first. For big indices you only need the top 60 to 100 names (Taiwan, Korea, China A: top 100).
   Keep the weights as they are (do NOT rescale to 100%): the page measures how much of the index the list covers.
4. Click Export to Excel, then in Excel choose Save As > CSV and name the file exactly as below.
5. On GitHub open this weights folder, press Add file > Upload files, drop the CSV in, and press Commit changes.
   The page rebuilds itself within a few minutes and the card changes to "Bloomberg index weights".

FILE NAMES (put them in this folder)
   spx.csv       S&P 500           (SPX Index)
   ndx.csv       Nasdaq-100        (NDX Index)
   hshares.csv   China H-shares    (HSCEI Index)
   ashares.csv   China A-shares    (SHSZ300 Index, the CSI 300)
   taiex.csv     Taiwan            (TWSE Index, the TAIEX)
   kospi.csv     Korea             (KOSPI Index)
   dow.csv       Dow 30            (INDU Index)  - optional, the Dow is price-weighted and is already exact without it

The script reads the first Ticker column and the weight column it finds (headers such as "Ticker", "Name", "Index Weight",
"% Wgt", "Weight" are recognised). Tickers like "NVDA UW Equity", "700 HK Equity", "2330 TT Equity", "005930 KS Equity",
"600519 C1 Equity" are translated automatically.
