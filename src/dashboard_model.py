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
# Presentation labels retain the published Education column on slicers, tooltips and tables.
EDUCATION_STYLES = [
    ("Secondary (high) school graduation certificate","Secondary school","#12766C"),
    ("No degree, certificate or diploma","No degree or diploma","#516D9B"),
    ("College/CEGEP","College / CEGEP","#98672F"),
    ("College, CEGEP or other non-university certificate or diploma from a program of 1 year to 2 years","College, 1–2 years","#735899"),
    ("Other trades certificate or diploma","Other trades certificate","#4F8759"),
    ("Bachelor's degree","Bachelor’s degree","#A65B70"),
    ("College, CEGEP or other non-university certificate or diploma from a program of 3 months to less than 1 year","College, 3–<12 months","#247F9D"),
    ("Registered Apprenticeship certificate","Registered apprenticeship","#977D3D"),
    ("Degree in medicine, dentistry, veterinary medicine or optometry","Professional degree","#445B82"),
    ("Master's degree","Master’s degree","#A56A45"),
    ("Earned doctorate degree","Doctorate","#58695A"),
    ("Not recorded","Not recorded","#C4CEC9")]
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
    "Data coverage": ('''VAR firstMonth = CALCULATE(MIN(Postings[Period date]),REMOVEFILTERS())
VAR lastMonth = CALCULATE(MAX(Postings[Period date]),REMOVEFILTERS())
RETURN IF(ISBLANK(firstMonth),"No data loaded",
    IF(firstMonth=lastMonth,FORMAT(lastMonth,"MMM yyyy","en-CA"),
        FORMAT(firstMonth,IF(YEAR(firstMonth)=YEAR(lastMonth),"MMM","MMM yyyy"),"en-CA") & " – " & FORMAT(lastMonth,"MMM yyyy","en-CA")))''',None),
    "Occupation detail heading": ('SELECTEDVALUE(Postings[Occupation and NOC],"All selected occupations")',None),
    "Full-time share": ('DIVIDE(CALCULATE([Location records],KEEPFILTERS(Postings[Employment type]="Full time")),[Location records])',"0.0%"),
    "Province count colour": ('''VAR recordsHere = [Location records]
RETURN SWITCH(TRUE(), ISBLANK(recordsHere),"#F0F3F1",recordsHere<1000,"#DAE9E1",
    recordsHere<5000,"#A4CEC0",recordsHere<10000,"#67AE99",recordsHere<25000,"#358B79",
    recordsHere<40000,"#12685E","#164C47")''',None),
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
    MEASURES["Displayed "+response] = (f'IF(HASONEVALUE(Indicators[Indicator]) && [Location records]>0,COALESCE([{response}],0))',NUMBER)

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
# Each half of a two-column ranking shares one maximum and the same alphabetical tie break.
for field_name, first, last, prefix in (("Province",7,None,"Province"),("City and province",5,10,"City")):
    eligible=f'FILTER(ALLSELECTED(Postings[{field_name}]),[Location records]>0'
    eligible+=f' && Postings[{field_name}]<>"Not recorded")' if prefix=="City" else ')'
    order=f'[Location records],DESC,Postings[{field_name}],ASC'
    leading=f'TOPN({first},__Candidates,{order})'
    remaining=f'EXCEPT(TOPN({last},__Candidates,{order}),{leading})' if last else f'EXCEPT(__Candidates,{leading})'
    for label, members in (("leading",leading),("remaining",remaining)):
        MEASURES[f"{prefix} {label} records"]=(f'''VAR __Candidates={eligible}
VAR __DisplayRows={members}
RETURN IF(CONTAINS(__DisplayRows,Postings[{field_name}],SELECTEDVALUE(Postings[{field_name}])),[Location records])''',NUMBER)
        MEASURES[f"{prefix} {label} openings"]=(f'IF(NOT ISBLANK([{prefix} {label} records]),[Advertised openings])',NUMBER)
    MEASURES[prefix+" scale maximum"]=(f'1.24*MAXX({eligible},[Location records])',NUMBER)
MEASURES["Hourly range graphic"] = ('''VAR upperScale = MAXX(ALLSELECTED(Postings[Province]),[Average hourly upper])
VAR l = 4+INT(140*DIVIDE([Average hourly lower],upperScale,0))
VAR u = 4+INT(140*DIVIDE([Average hourly upper],upperScale,0))
VAR m = 4+INT(140*DIVIDE([Average hourly midpoint],upperScale,0))
RETURN IF([Hourly records]>0,"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='150' height='18'><path d='M4 9H144' stroke='%23D6E0DB'/><path d='M"&l&" 9H"&u&"' stroke='%2372978C' stroke-width='4'/><circle cx='"&m&"' cy='9' r='4' fill='%2308675F'/></svg>")''',None)

def education_key():
    ordering=",".join(f'"{label}",{i}' for i,(_,label,_) in enumerate(EDUCATION_STYLES,1))
    colours=",".join(f'"{label}","{colour.replace("#","%23")}"' for _,label,colour in EDUCATION_STYLES)
    return f'''VAR __labelsInScope = VALUES(Postings[Education label])
VAR __orderedLabels = ADDCOLUMNS(__labelsInScope,"@order",SWITCH(Postings[Education label],{ordering},99))
VAR __perColumn = MAX(1,ROUNDUP(COUNTROWS(__orderedLabels)/3,0))
RETURN IF([Location records]>0,"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='620' height='" & (__perColumn*24+6) & "'>" &
    CONCATENATEX(__orderedLabels,
        VAR __nm = Postings[Education label]
        VAR __ord = [@order]
        VAR __pos = COUNTROWS(FILTER(__orderedLabels,[@order]<__ord || ([@order]=__ord && Postings[Education label]<__nm)))+0
        VAR __x = 2+207*INT(__pos/__perColumn)
        VAR __y = 3+24*MOD(__pos,__perColumn)
        VAR __labelText = SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(__nm,"&","&amp;"),"<","&lt;"),">","&gt;")
        RETURN "<rect x='" & __x & "' y='" & (__y+3) & "' width='12' height='10' rx='2' fill='" &
          SWITCH(__nm,{colours},"%23586862") & "'/><text x='" & (__x+19) & "' y='" & (__y+13) &
          "' font-family='Segoe UI, sans-serif' font-size='12' fill='%232F4847'>" & __labelText & "</text>",
        "") & "</svg>")'''
MEASURES["Education colour key"]=(education_key(),None)

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
    short_names=",".join(f'{quoted(raw)},{quoted(label)}' for raw,label,_ in EDUCATION_STYLES)
    columns.append({"name":"Education label","type":"calculated","dataType":"string","summarizeBy":"none",
                    "expression":f"SWITCH(Postings[Education],{short_names},Postings[Education])"})
    image_measures={"Hourly range graphic","Education colour key"}
    measures=[{"name":k,"expression":v,**({"formatString":fmt} if fmt else {"dataCategory":"ImageUrl"} if k in image_measures else {})}
              for k,(v,fmt) in MEASURES.items()]
    postings={"name":"Postings","columns":columns,"measures":measures,
              "partitions":[{"name":"Postings","mode":"import","source":{"type":"m","expression":m}}]}
    indicators={"name":"Indicators","columns":[{"name":"Indicator","dataType":"string","sourceColumn":"Indicator","summarizeBy":"none"}],
                "partitions":[{"name":"Indicators","mode":"import","source":{"type":"m","expression":[
                    '#table(type table [Indicator=text], {'+','.join('{'+quoted(x)+'}' for x in FLAGS)+'})']}}]}
    return {"name":"Job Bank","compatibilityLevel":1600,"model":{"culture":"en-CA","sourceQueryCulture":"en-CA",
            "defaultPowerBIDataSourceVersion":"powerBI_V3","tables":[postings,indicators]}}
