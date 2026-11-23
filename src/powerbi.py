"""Generate the D4.2 wireframes (figures 1–5) as a native Power BI project."""
import hashlib
import json
from pathlib import Path

from database import HOST, PORT, DATABASE
from dashboard_model import COLUMNS, MEASURES, build_model

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "powerbi"
REPORT = DEST / "Job Bank.Report"
MODEL = DEST / "Job Bank.SemanticModel"
DEF = REPORT / "definition"
BASE = "https://developer.microsoft.com/json-schemas/fabric/"
RS = "item/report/definition/"
FILTERS = [("Occupation and NOC","Occupation / NOC"),("Province","Province"),("City","City"),
           ("Month","Time period"),("Education","Education level")]
PAGES = ["Overview","Demand Over Time","Geographic Distribution","Qualifications","Compensation","Work Conditions"]
DETAIL = "Occupation detail"
def key(s):
    return hashlib.sha256(s.encode()).hexdigest()[:20]
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
def schema(path, kind, **data):
    write(path,{"$schema":BASE+kind+"/schema.json",**data})
def literal(s):
    return {"expr":{"Literal":{"Value":s}}}
def string(s):
    return literal("'"+s.replace("'","''")+"'")
def color(s):
    return {"solid":{"color":string(s)}}
def prop(**kw):
    return [{"properties":kw}]
def field(n):
    entity="Indicators" if n=="Indicator" else "Postings"
    if n not in MEASURES and n not in COLUMNS and n not in ("Indicator","Map province"):
        raise KeyError(n)
    return {"Measure" if n in MEASURES else "Column":{"Expression":{"SourceRef":{"Entity":entity}},"Property":n}}
def projection(n):
    f=field(n)
    entity=next(iter(f.values()))["Expression"]["SourceRef"]["Entity"]
    return {"field":f,"queryRef":f"{entity}.{n}","nativeQueryRef":n}
def visual(page,title,typ,xy,roles=None,sort=None,objs=None,container=None,sync=None,required_measure=None):
    x,y,w,h=xy
    vid=key(page.name+title)
    config={"title":prop(show=literal("true"),text=string(title),fontColor=color("#243950"),
                         fontSize=literal("11D"),bold=literal("true")),
            "background":prop(show=literal("true"),color=color("#FFFFFF"),transparency=literal("0D")),
            "border":prop(show=literal("true"),color=color("#D5DEE8"),radius=literal("7D"))}
    config.update(container or {})
    vis={"visualType":typ,"visualContainerObjects":config}
    if roles:
        state={role:{"projections":[projection(n) for n in names]} for role,names in roles.items()}
        vis["query"]={"queryState":state}
        if sort:
            vis["query"]["sortDefinition"]={"sort":[{"field":field(sort[0]),"direction":sort[1]}]}
    if objs: vis["objects"]=objs
    if sync: vis["syncGroup"]={"groupName":"D42 "+sync,"fieldChanges":True,"filterChanges":True}
    extra={}
    if required_measure:
        measure={"Measure":{"Expression":{"SourceRef":{"Source":"p"}},"Property":required_measure}}
        extra["filterConfig"]={"filters":[{
            "name":"Filter"+key(title+" ranked values"),"field":field(required_measure),"type":"Advanced",
            "filter":{"Version":2,"From":[{"Name":"p","Entity":"Postings","Type":0}],
                      "Where":[{"Condition":{"Not":{"Expression":{"Comparison":{
                          "ComparisonKind":0,"Left":measure,"Right":{"Literal":{"Value":"null"}}}}}}}]}
        }]}
    schema(page/"visuals"/vid/"visual.json",RS+"visualContainer/2.1.0",name=vid,
           position={"x":x,"y":y,"width":w,"height":h,"z":y*10+x,"tabOrder":y*10+x},visual=vis,**extra)

def heading(page,name):
    text={"general":prop(paragraphs=[
        {"textRuns":[{"value":"CANADA LABOUR MARKET ANALYTICS","textStyle":{"fontSize":"17pt","fontWeight":"bold","color":"#243950"}}]},
        {"textRuns":[{"value":name,"textStyle":{"fontSize":"14pt","fontWeight":"bold","color":"#526E89"}}]}])}
    hide={"title":prop(show=literal("false")),"background":prop(show=literal("false")),"border":prop(show=literal("false"))}
    visual(page,"Report heading","textbox",(34,9,800,70),objs=text,container=hide)
    for i,(n,label) in enumerate(FILTERS):
        visual(page,label,"slicer",(34+i*243,89,242,72),{"Values":[n]},
               objs={"data":prop(mode=string("Dropdown")),"header":prop(show=literal("false"))},sync=n)
    labels = ("Overview","Demand","Geography","Qualifications","Compensation","Conditions")
    for i,(target,label) in enumerate(zip(PAGES,labels)):
        active = target == name
        button = {"text":[{"properties":{"show":literal("true")}},
                          {"selector":{"id":"default"},"properties":{
                              "text":string(label),"fontColor":color("#243950"),"bold":literal("true" if active else "false")}}]}
        frame = {"title":prop(show=literal("false")),
                 "background":prop(show=literal("true"),color=color("#DFE8EF" if active else "#FFFFFF"),transparency=literal("0D")),
                 "visualLink":prop(show=literal("true"),type=string("PageNavigation"),navigationSection=string(key(target)))}
        # Reuse the previous navigator container for the first link when upgrading an existing report.
        visual(page,"Page navigation" if i==0 else f"Navigate to {target}", "actionButton",
               (34+i*202,665,202,45),objs=button,container=frame)
def card(page,title,n,x):
    visual(page,title,"card",(x,174,394,90),{"Values":[n]},objs={"categoryLabels":prop(show=literal("false")),
           "labels":prop(labelDisplayUnits=literal("1D"),fontSize=literal("23D"),color=color("#344F69"))})
def bar(page,title,cat,metric,pos,tips=(),kind="clusteredBarChart",ranked=False):
    roles={"Category":[cat],"Y":[metric]}
    if tips: roles["Tooltips"]=list(tips)
    visual(page,title,kind,pos,roles,(metric,"Descending"),required_measure=metric if ranked else None)
def all_pages():
    for name in PAGES+[DETAIL]:
        page=DEF/"pages"/key(name)
        extra={}
        if name==DETAIL:
            fid="Filter"+key("Occupation detail filter")
            extra={"visibility":"HiddenInViewMode","filterConfig":{"filters":[{"name":fid,"field":field("Occupation and NOC"),
                    "type":"Categorical","howCreated":"Drillthrough"}]},"pageBinding":{"name":"Detail","type":"Drillthrough",
                    "parameters":[{"name":"Param"+fid,"boundFilter":fid,"fieldExpr":field("Occupation and NOC")}]}}
        schema(page/"page.json",RS+"page/2.0.0",name=page.name,displayName=name,displayOption="FitToPage",
               height=720,width=1280,objects={"background":prop(color=color("#F3F5F7"),transparency=literal("0D"))},**extra)
        heading(page,name)
        if name=="Demand Over Time":
            for x,(t,n) in zip((34,443,852),[("Job postings · location records","Location records"),
                    ("Advertised vacancies","Advertised openings"),("Latest month vs previous month · postings","Monthly change")]):card(page,t,n,x)
            visual(page,"Monthly job demand · location records and openings","lineChart",(34,279,735,370),
                   {"Category":["Month"],"Y":["Location records","Advertised openings"]},("Month","Ascending"),
                   objs={"valueAxis":prop(showAxisTitle=literal("false"))})
            bar(page,"Top 10 occupations · posting locations","Occupation and NOC","Top occupation records",(785,279,461,370),["Advertised openings"],ranked=True)
        elif name=="Geographic Distribution":
            geo={"geoJson":{"type":string("shared"),"name":string("canada.provinces.topo"),
                 "content":{"expr":{"ResourcePackageItem":{"PackageName":"SharedResources","PackageType":2,"ItemName":"canada.provinces.topo"}}}}}
            visual(page,"Canada · postings by province or territory","shapeMap",(34,174,731,475),
                {"Category":["Map province"],"Value":["Location records"],"Tooltips":["Advertised openings"]},
                objs={"shape":prop(map=geo,projectionEnum=string("orthographic"))})
            bar(page,"Postings by province or territory","Province","Location records",(781,174,465,229),["Advertised openings"])
            bar(page,"Top 10 cities · posting locations","City and province","Top city records",(781,418,465,231),["Advertised openings"],ranked=True)
        elif name=="Qualifications":
            visual(page,"Education requirements by occupation · posting locations","barChart",(34,174,590,475),
                   {"Category":["Occupation and NOC"],"Series":["Education"],"Y":["Location records"]})
            bar(page,"Experience requirements · posting locations","Experience","Location records",(640,174,606,227))
            visual(page,"Occupation and qualification comparison","tableEx",(640,417,606,232),
                   {"Values":["Occupation and NOC","Education","Experience","Location records"]},("Location records","Descending"))
        elif name=="Compensation":
            for x,(t,n) in zip((34,443,852),[("Average advertised midpoint · CAD/hour","Average hourly midpoint"),
                    ("Median advertised midpoint · CAD/hour","Median hourly midpoint"),("Comparable hourly records","Hourly records")]):card(page,t,n,x)
            bar(page,"Average pay · CAD/hour · 10 occupations with most hourly records","Occupation and NOC","Hourly pay in leading occupations",
                (34,279,590,370),["Hourly records","Average hourly lower","Average hourly upper"],ranked=True)
            visual(page,"Average range by province · CAD/hour · marker is midpoint","tableEx",(640,279,606,370),
                   {"Values":["Province","Hourly range graphic","Average hourly lower","Average hourly upper","Average hourly midpoint"]},
                   ("Average hourly midpoint","Descending"),objs={"grid":prop(imageHeight=literal("18D"))})
        elif name=="Work Conditions":
            visual(page,"Employment type · posting locations","donutChart",(34,174,384,475),
                   {"Category":["Employment type"],"Y":["Location records"]})
            visual(page,"Weekly hours · midpoint of reported range","clusteredColumnChart",(433,174,386,475),
                   {"Category":["Weekly hours band"],"Y":["Location records"]},("Weekly hours band","Ascending"))
            visual(page,"Work arrangements and benefits · records","barChart",(834,174,412,475),
                   {"Category":["Indicator"],"Y":["Yes","No","Not recorded"]})
        elif name=="Overview":
            for x,(t,n) in zip((34,443,852),[("Posting locations","Location records"),("Advertised openings","Advertised openings"),
                                            ("Comparable hourly records","Hourly records")]):card(page,t,n,x)
            visual(page,"Posting locations by first-posting month and source","clusteredColumnChart",(34,279,610,370),
                   {"Category":["Month"],"Series":["Source"],"Y":["Location records"]},("Month","Ascending"))
            visual(page,"Occupation summary · right-click to drill through","tableEx",(660,279,586,370),
                   {"Values":["Occupation and NOC","Location records","Advertised openings","Average hourly midpoint"]},("Location records","Descending"))
        else:
            visual(page,"Occupation by month","tableEx",(34,174,594,475),
                   {"Values":["Occupation and NOC","Month","Location records","Advertised openings","Hourly records","Median hourly midpoint"]},("Month","Ascending"))
            visual(page,"Locations within province and economic region","tableEx",(644,174,602,475),
                   {"Values":["Province","Economic region","City","Location records","Advertised openings"]},("Location records","Descending"))
            visual(page,"Back to selection","actionButton",(1035,17,211,49),objs={"text":prop(show=literal("true"),text=string("Back to selection"))},
                   container={"visualLink":prop(show=literal("true"),type=string("Back"))})
def build():
    schema(DEST/"Job Bank.pbip","pbip/pbipProperties/1.0.0",version="1.0",artifacts=[{"report":{"path":REPORT.name}}],settings={"enableAutoRecovery":True})
    schema(REPORT/"definition.pbir","item/report/definitionProperties/2.0.0",version="4.0",datasetReference={"byPath":{"path":"../"+MODEL.name}})
    schema(MODEL/"definition.pbism","item/semanticModel/definitionProperties/1.0.0",version="1.0",settings={})
    write(MODEL/"model.bim",build_model(HOST,PORT,DATABASE))
    schema(DEF/"version.json",RS+"versionMetadata/1.0.0",version="2.0.0")
    nv={"visual":"2.1.0","report":"3.0.0","page":"2.0.0"}
    theme={"name":"D42Blueprint","dataColors":["#526E89","#94A5B7","#CBD4DE","#718D9F","#334D67","#AAB8C4","#84939E"],
           "background":"#FFFFFF","foreground":"#25384B","tableAccent":"#526E89"}
    write(REPORT/"StaticResources/RegisteredResources/D42Blueprint.json",theme)
    schema(DEF/"report.json",RS+"report/3.0.0",themeCollection={
        "baseTheme":{"name":"CY24SU10","type":"SharedResources","reportVersionAtImport":nv},
        "customTheme":{"name":"D42Blueprint","type":"RegisteredResources","reportVersionAtImport":nv}},
        resourcePackages=[{"name":"SharedResources","type":"SharedResources","items":[
            {"name":"CY24SU10","path":"BaseThemes/CY24SU10.json","type":"BaseTheme"},
            {"name":"canada.provinces.topo","path":"Shapemaps/canada.provinces.topo.json","type":"ShapeMap"}]},
            {"name":"RegisteredResources","type":"RegisteredResources","items":[
            {"name":"D42Blueprint","path":"D42Blueprint.json","type":"CustomTheme"}]}])
    all_pages()
    schema(DEF/"pages/pages.json",RS+"pagesMetadata/1.0.0",pageOrder=[key(x) for x in PAGES+[DETAIL]],activePageName=key("Demand Over Time"))
if __name__=="__main__":
    build()
    print("Wrote the D4.2 Power BI project.")
