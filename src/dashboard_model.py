"""Fields and DAX measures shared by the D4.2 report and its generator."""
COLUMNS = {
    "Snapshot ID":"string", "First posted":"string", "Month":"string", "Source":"string",
    "NOC":"string", "Occupation":"string", "Province":"string", "Economic region":"string",
    "Education":"string", "Experience":"string", "Employment type":"string", "Employment term":"string",
    "Telework flag":"string", "Weekend flag":"string", "Pay period":"string", "Pay status":"string",
    "Vacancies":"int64", "Lower amount":"double", "Upper amount":"double", "Midpoint amount":"double",
    "City":"string", "City and province":"string", "Occupation and NOC":"string", "Weekly hours band":"string",
    "Hours sort":"int64", "Dental flag":"string", "Medical flag":"string", "Evening flag":"string",
    "Period date":"dateTime"
}
NUMBER, MONEY = "#,0", "$#,0.00"
def hourly(aggregate, column):
    return f'CALCULATE({aggregate}(Postings[{column}]), KEEPFILTERS(Postings[Pay period] = "Hour"))'
MEASURES = {
    "Location records": ("COUNTROWS(Postings)", NUMBER),
    "Advertised openings": ("SUM(Postings[Vacancies])", NUMBER),
    "Hourly records": (hourly("COUNT","Midpoint amount"),NUMBER),
    "Average hourly midpoint": (hourly("AVERAGE","Midpoint amount"),MONEY),
    "Median hourly midpoint": (hourly("MEDIAN","Midpoint amount"),MONEY),
    "Average hourly lower": (hourly("AVERAGE","Lower amount"),MONEY),
    "Average hourly upper": (hourly("AVERAGE","Upper amount"),MONEY),
    "Median hourly lower": (hourly("MEDIAN","Lower amount"),MONEY),
    "Median hourly upper": (hourly("MEDIAN","Upper amount"),MONEY),
    "Monthly change": ('''VAR d = MAX(Postings[Period date])
VAR prior = EDATE(d,-1)
VAR currentCount = CALCULATE([Location records],REMOVEFILTERS(Postings[Month]),Postings[Period date]=d)
VAR priorCount = CALCULATE([Location records],REMOVEFILTERS(Postings[Month]),Postings[Period date]=prior)
RETURN DIVIDE(currentCount-priorCount,priorCount)''',"+0.0%;-0.0%;0.0%"),
}
FLAGS = {"Virtual work":"Telework flag","Weekend":"Weekend flag","Evening":"Evening flag",
         "Dental benefit":"Dental flag","Medical benefit":"Medical flag","Permanent term":"Employment term"}
for response in ("Yes","No","Not recorded"):
    branches = []
    for label,column in FLAGS.items():
        condition = f'Postings[{column}]="{response}"'
        if label == "Permanent term" and response == "Yes":
            condition = 'Postings[Employment term]="Permanent employment"'
        if label == "Permanent term" and response == "No":
            condition = 'NOT(Postings[Employment term] IN {"Permanent employment","Not recorded"})'
        branches.append(f'"{label}", CALCULATE([Location records],KEEPFILTERS({condition}))')
    MEASURES[response] = ("SWITCH(SELECTEDVALUE(Indicators[Indicator]),"+",\n".join(branches)+")", NUMBER)

def top_records(field, rank_measure, display_measure=None):
    display_measure = display_measure or rank_measure
    return f'''VAR __EligibleCategories =
    FILTER(ALLSELECTED(Postings[{field}]), Postings[{field}] <> "Not recorded" && [{rank_measure}] > 0)
VAR __TopCategories =
    TOPN(10, __EligibleCategories, [{rank_measure}], DESC, Postings[{field}], ASC)
RETURN IF(CONTAINS(__TopCategories, Postings[{field}], SELECTEDVALUE(Postings[{field}])), [{display_measure}])'''
MEASURES["Top occupation records"]=(top_records("Occupation and NOC","Location records"),NUMBER)
MEASURES["Top city records"]=(top_records("City and province","Location records"),NUMBER)
MEASURES["Hourly pay in leading occupations"]=(top_records("Occupation and NOC","Hourly records","Average hourly midpoint"),MONEY)
MEASURES["Hourly range graphic"] = ('''VAR upperScale = MAXX(ALLSELECTED(Postings[Province]),[Average hourly upper])
VAR l = 4+INT(140*DIVIDE([Average hourly lower],upperScale,0))
VAR u = 4+INT(140*DIVIDE([Average hourly upper],upperScale,0))
VAR m = 4+INT(140*DIVIDE([Average hourly midpoint],upperScale,0))
RETURN IF([Hourly records]>0,"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='18'><path d='M"&l&" 9H"&u&"' stroke='%239aaabd' stroke-width='4'/><rect x='"&(m-3)&"' y='5' width='7' height='8' fill='%23526e89'/></svg>")''',None)

def build_model(host,port,database):
    def quoted(s):
        return '"' + s.replace('#','#(#)').replace('"','""') + '"'
    m = ["let",f"    Source = MySQL.Database({quoted(f'{host}:{port}')}, {quoted(database)}, [ReturnSingleDatabase=true]),",
         f'    Postings = Source{{[Schema={quoted(database)}, Item="powerbi_postings"]}}[Data]',"in","    Postings"]
    columns = [{"name":k,"dataType":t,"sourceColumn":k,"summarizeBy":"none"} for k,t in COLUMNS.items()]
    for c in columns:
        if c["name"]=="Weekly hours band": c["sortByColumn"]="Hours sort"
        if c["name"]=="Hours sort": c["isHidden"]=True
    # The native Canada map uses unaccented English names. Preserve the published province on every slicer.
    columns.append({"name":"Map province","type":"calculated","dataType":"string","summarizeBy":"none",
                    "dataCategory":"StateOrProvince","expression":'SUBSTITUTE(Postings[Province],"Québec","Quebec")'})
    measures=[{"name":k,"expression":v,**({"formatString":fmt} if fmt else {"dataCategory":"ImageUrl"})}
              for k,(v,fmt) in MEASURES.items()]
    postings={"name":"Postings","columns":columns,"measures":measures,
              "partitions":[{"name":"Postings","mode":"import","source":{"type":"m","expression":m}}]}
    indicators={"name":"Indicators","columns":[{"name":"Indicator","dataType":"string","sourceColumn":"Indicator","summarizeBy":"none"}],
                "partitions":[{"name":"Indicators","mode":"import","source":{"type":"m","expression":[
                    '#table(type table [Indicator=text], {'+','.join('{'+quoted(x)+'}' for x in FLAGS)+'})']}}]}
    return {"name":"Job Bank","compatibilityLevel":1600,"model":{"culture":"en-CA","sourceQueryCulture":"en-CA",
            "defaultPowerBIDataSourceVersion":"powerBI_V3","tables":[postings,indicators]}}
