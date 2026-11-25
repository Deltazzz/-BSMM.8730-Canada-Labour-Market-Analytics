"""Generate the approved Job Bank dashboard as native, MySQL-backed Power BI visuals."""
import hashlib
import json
from pathlib import Path

from database import HOST, PORT, DATABASE
from dashboard_model import COLUMNS, EDUCATION_STYLES, MEASURES, build_model

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
WIDTH, HEIGHT = 1440, 810
INK, SECONDARY, GREEN, BLUE = "#172B2B", "#495E5E", "#12766C", "#516D9B"
DARK, PALE, RULE, MISSING = "#104942", "#E1F1EB", "#D6E0DB", "#C4CEC9"
WHITE, CANVAS = "#FFFFFF", "#F6F8F6"
FONT = "Segoe UI"
CHART_TYPES = {"lineChart","clusteredBarChart","clusteredColumnChart","barChart","donutChart","shapeMap","tableEx"}
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
def expr(value):
    if isinstance(value,dict): return value
    if isinstance(value,bool): return literal(str(value).lower())
    if isinstance(value,(int,float)): return literal(f"{value}D")
    return color(value) if value.startswith("#") else string(value)
def fmt(**kw):
    return prop(**{k:expr(v) for k,v in kw.items()})
def field(n):
    entity="Indicators" if n=="Indicator" else "Postings"
    if n not in MEASURES and n not in COLUMNS and n not in ("Indicator","Map province","Education label"):
        raise KeyError(n)
    return {"Measure" if n in MEASURES else "Column":{"Expression":{"SourceRef":{"Entity":entity}},"Property":n}}
def projection(n):
    f=field(n)
    entity=next(iter(f.values()))["Expression"]["SourceRef"]["Entity"]
    return {"field":f,"queryRef":f"{entity}.{n}","nativeQueryRef":n}
def visual(page,title,typ,xy,roles=None,sort=None,objs=None,container=None,sync=None,required_measure=None,
           caption=None,subtitle=None,aliases=None,mobile=None,mobile_caption=None,mobile_objects=None):
    x,y,w,h=xy
    vid=key(page.name+title)
    config={"title":fmt(show=bool(caption),text=caption or title,fontColor=INK,fontFamily=FONT,fontSize=15,bold=True),
            "background":fmt(show=False),"border":fmt(show=False),
            "padding":fmt(top=2,bottom=2,left=4,right=4)}
    if subtitle:
        config["subTitle"]=fmt(show=True,text=subtitle,fontFamily=FONT,fontSize=10,fontColor=SECONDARY)
    config.update(container or {})
    vis={"visualType":typ,"visualContainerObjects":config}
    if roles:
        state={role:{"projections":[projection(n) for n in names]} for role,names in roles.items()}
        for role in state.values():
            for item in role["projections"]:
                label=(aliases or {}).get(item["nativeQueryRef"])
                if label:item["displayName"]=label
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
    if mobile:
        mx,my,mw,mh=mobile
        if typ!="slicer" and title!="Report heading":
            has_kpis=page.name in {key(n) for n in ("Overview","Demand Over Time","Compensation")}
            extra_card_space=20*min(3,max(0,(my-232)//78)) if has_kpis else 0
            my+=110+extra_card_space
            if typ=="card" and y==239:
                mh+=20
        overrides={"background":fmt(show=True,color=DARK if typ=="card" and y==239 else WHITE,transparency=0)}
        if mobile_caption:
            overrides["title"]=fmt(show=True,text=mobile_caption,fontSize=12,fontColor=INK,bold=True)
        schema(page/"visuals"/vid/"mobile.json",RS+"visualContainerMobileState/2.1.0",
               position={"x":mx,"y":my,"width":mw,"height":mh,"z":my,"tabOrder":my+mx},
               visualContainerObjects=overrides,**({"objects":mobile_objects} if mobile_objects else {}))

def textbox(page, identifier, value, box, size, *, weight=False, colour=INK, mobile=None):
    run={"value":value,"textStyle":{"fontFamily":FONT,"fontSize":f"{size}pt",
         "fontWeight":"bold" if weight else "normal","color":colour}}
    mobile_objects=None
    if mobile:
        small_run={**run,"textStyle":{**run["textStyle"],"fontSize":"18pt"}}
        mobile_objects={"general":prop(paragraphs=[{"textRuns":[small_run]}])}
    visual(page,identifier,"textbox",box,objs={"general":prop(paragraphs=[{"textRuns":[run]}])},
           mobile=mobile,mobile_objects=mobile_objects)

def state(properties, selector):
    return {"selector":selector,"properties":{k:expr(v) for k,v in properties.items()}}

def button(page,identifier,label,box,action,*,active=False,secondary=False,mobile=None):
    tint="#08675F" if active or secondary else SECONDARY
    objects={"shape":fmt(tileShape="rectangleRoundedByPixel",roundEdge=10),
             "text":fmt(show=True)+[state({"text":label,"fontFamily":FONT,"fontSize":12,
                     "fontColor":tint,"bold":active or secondary},{"id":"default"})],
             "outline":fmt(show=False)+[state({"show":False,"transparency":100},{"id":"default"})],
             "fill":fmt(show=False)+[state({"show":True,"fillColor":PALE,"transparency":0},{"id":"onHover"})],
             "icon":fmt(show=False)}
    visual(page,identifier,"actionButton",box,objs=objects,container={"visualLink":fmt(show=True,**action)},mobile=mobile)

SUBTITLES=["New Job Bank posting locations, advertised openings and hourly pay across Canada.",
    "Monthly changes in Job Bank posting locations and advertised openings.",
    "Where employers advertised openings across provinces, territories and cities.",
    "Education and experience requirements recorded in Job Bank postings.",
    "Advertised hourly pay in Canadian dollars, using comparable pay ranges.",
    "Employment types, weekly hours, schedules and benefits in Job Bank postings.",
    "Monthly demand and geographic detail for the selected occupation."]

def heading(page,name):
    idx=(PAGES+[DETAIL]).index(name)
    textbox(page,"Brand","Canada Labour Market Analytics",(84,1,540,42),14,weight=True)
    textbox(page,"Report heading",name,(39,69,1100,62),30,weight=True,mobile=(5,4,308,76))
    textbox(page,"Page description",SUBTITLES[idx],(40,121,1350,34),12,colour=SECONDARY)
    textbox(page,"Coverage label","Data coverage",(1119,6,115,33),10,colour=SECONDARY)
    visual(page,"Coverage dates","card",(1232,2,165,37),{"Values":["Data coverage"]},
           objs={"categoryLabels":fmt(show=False),"labels":fmt(fontSize=12,fontFamily=FONT,bold=True,color=INK)})
    divs=[44,369,609,824,1104,1396]
    for i,(n,label) in enumerate(FILTERS):
        left,right=divs[i:i+2]
        visual(page,label,"slicer",(left+8,148,right-left-16,59),{"Values":[n]},
               caption=label,container={"title":fmt(show=True,text=label,fontColor=SECONDARY,fontSize=10,fontFamily=FONT,bold=True)},
               objs={"data":fmt(mode="Dropdown"),"header":fmt(show=False),"items":fmt(textSize=11,fontFamily=FONT,fontColor=INK),
                     "dropdown":fmt(borderColor=RULE,borderRadius=5,iconColor=SECONDARY)},sync=n,
               mobile=(5 if not i%2 else 162,84+(i//2)*84,151 if i<4 else 308,80))
    labels=("Overview","Demand","Geography","Qualifications","Compensation","Conditions")
    widths=(155,150,164,183,184,161)
    x=(WIDTH-sum(widths))/2
    for i,(target,label,w) in enumerate(zip(PAGES,labels,widths)):
        button(page,"Page navigation" if i==0 else "Navigate to "+target,label,
               (x+4,752,w-8,46),{"type":"PageNavigation","navigationSection":key(target)},active=target==name)
        x+=w

def card(page,identifier,measure,x,label,note,index):
    visual(page,identifier,"card",(x,239,425,62),{"Values":[measure]},caption=label,
           container={"title":fmt(show=True,text=label,fontSize=11,fontFamily=FONT,fontColor="#DEF0E9",bold=True)},
           objs={"categoryLabels":fmt(show=False),"labels":fmt(labelDisplayUnits=1,fontSize=28,fontFamily=FONT,bold=True,color=WHITE)},
           mobile=(5,232+index*78,308,72))
    textbox(page,identifier+" note",note,(x,299,427,36),9,colour="#DEF0E9")

def chart_format(typ):
    axis=fmt(showAxisTitle=False,fontSize=10,fontFamily=FONT,labelColor=SECONDARY,maxMarginFactor=44)
    if typ=="shapeMap":
        return {"defaultColors":fmt(borderColor="#62877C",borderThickness=1)}
    if typ=="tableEx":
        return {"columnHeaders":fmt(fontFamily=FONT,fontSize=10,bold=True,fontColor=SECONDARY,backColor="#F0F4F1",wordWrap=True),
                "values":fmt(fontFamily=FONT,fontSize=11,fontColorPrimary=INK,fontColorSecondary=INK,
                             backColorPrimary=WHITE,backColorSecondary=WHITE,wordWrap=True),
                "grid":fmt(gridHorizontal=True,gridHorizontalColor=RULE,gridVertical=False,rowPadding=4,imageHeight=18,imageWidth=90),
                "total":fmt(totals=True,bold=True,fontColor=INK,backColor=PALE,fontSize=11)}
    legend=fmt(show=True,showTitle=False,position="Top",fontSize=10,fontFamily=FONT,labelColor=SECONDARY)
    if typ=="donutChart":
        return {"legend":fmt(show=True,position="BottomCenter",showTitle=False,fontSize=10,labelColor=SECONDARY),
                "labels":fmt(show=True,labelStyle="Data",labelDisplayUnits=1,fontSize=10,color=INK),
                "slices":fmt(innerRadiusRatio=70)}
    return {"categoryAxis":axis,"valueAxis":fmt(showAxisTitle=False,fontFamily=FONT,fontSize=9,labelColor=SECONDARY,
               gridlineColor=RULE,gridlineShow=typ in ("lineChart","clusteredColumnChart"),show=typ!="clusteredBarChart"),
            "legend":legend,"labels":fmt(show=typ!="barChart",fontSize=10,fontFamily=FONT,color=INK,labelDisplayUnits=1),
            "dataPoint":fmt(defaultColor=GREEN)}

def chart(page,identifier,caption,subtitle,typ,box,roles,mobile,sort=None,extra=None,ranked=None,aliases=None,mobile_caption=None):
    objects=chart_format(typ)
    objects.update(extra or {})
    if typ=="tableEx":
        widths={
            "Occupation summary · right-click to drill through":[335,87,103,116],
            "Occupation and qualification comparison":[215,157,135,77],
            "Average range by province · CAD/hour · marker is midpoint":[157,107,95,95,112],
            "Response counts":[133,78,78,119],
            "Employment type counts":[254,94],
            "Education legend":[609],
            "Occupation by month":[158,79,73,75,85,93],
            "Locations within province and economic region":[128,189,107,79,90],
        }[identifier]
        objects["columnHeaders"][0]["properties"]["autoSizeColumnWidth"]=expr(False)
        objects["columnWidth"]=[state({"value":w},{"metadata":projection(f)["queryRef"]}) for f,w in zip(roles["Values"],widths)]
    visual(page,identifier,typ,box,roles,sort=sort,objs=objects,caption=caption,subtitle=subtitle,
           required_measure=ranked,aliases=aliases,mobile=(5,mobile[0],308,mobile[1]),mobile_caption=mobile_caption)

def data_colour(category, value, hexcolour):
    entity="Indicators" if category=="Indicator" else "Postings"
    comparison={"Comparison":{"ComparisonKind":0,"Left":field(category),
                "Right":{"Literal":{"Value":"'"+value.replace("'","''")+"'"}}}}
    return state({"fill":hexcolour},{"data":[{"scopeId":comparison}]})

def measure_colour(name,hexcolour):
    return state({"fill":hexcolour},{"metadata":"Postings."+name})

def roles(cat,measure,tips=()):
    fields={"Category":[cat],"Y":[measure]}
    if tips:fields["Tooltips"]=list(tips)
    return fields

def descending(field_name):return (field_name,"Descending")

def all_pages():
    for idx,name in enumerate(PAGES+[DETAIL]):
        page=DEF/"pages"/key(name)
        extra={}
        if name==DETAIL:
            fid="Filter"+key("Occupation detail filter")
            extra={"visibility":"HiddenInViewMode","filterConfig":{"filters":[{"name":fid,"field":field("Occupation and NOC"),
                    "type":"Categorical","howCreated":"Drillthrough"}]},"pageBinding":{"name":"Detail","type":"Drillthrough",
                    "parameters":[{"name":"Param"+fid,"boundFilter":fid,"fieldExpr":field("Occupation and NOC")}]}}
        artwork=f"Layout{idx}.png"
        image={"image":{"name":string(artwork),"url":{"expr":{"ResourcePackageItem":{
               "PackageName":"RegisteredResources","PackageType":1,"ItemName":artwork}}},"scaling":string("Fit")}}
        schema(page/"page.json",RS+"page/2.0.0",name=page.name,displayName=name,displayOption="FitToPage",
               height=HEIGHT,width=WIDTH,objects={"background":fmt(color=CANVAS,image=image,transparency=0)},**extra)
        heading(page,name)
        kpis={
            "Overview":[("Posting locations","Location records","Posting locations","Unique Job Bank location records"),
                        ("Advertised openings","Advertised openings","Advertised openings","Vacancies summed across records"),
                        ("Comparable hourly records","Hourly records","Comparable hourly records","Positive, ordered hourly pay ranges")],
            "Demand Over Time":[("Job postings · location records","Location records","Posting locations","Records in the current selection"),
                       ("Advertised vacancies","Advertised openings","Advertised openings","Vacancies summed across records"),
                       ("Latest month vs previous month · postings","Monthly change","Monthly change","Latest vs previous month · posting locations")],
            "Compensation":[("Average advertised midpoint · CAD/hour","Average hourly midpoint","Average hourly midpoint","CAD per hour"),
                    ("Median advertised midpoint · CAD/hour","Median hourly midpoint","Median hourly midpoint","CAD per hour"),
                    ("Comparable hourly records","Hourly records","Comparable hourly records","Records included in both pay metrics")]}
        for i,(identifier,measure,label,note) in enumerate(kpis.get(name,[])):
            card(page,identifier,measure,62+i*451,label,note,i)
        if name=="Overview":
            chart(page,"Posting locations by first-posting month and source","Posting locations by source","New records by first-posting month",
                  "clusteredColumnChart",(63,371,579,311),{"Category":["Month"],"Series":["Source"],"Y":["Location records"]},(475,247),
                  ("Month","Ascending"),{"dataPoint":[data_colour("Source","Direct",GREEN),data_colour("Source","External",BLUE)]})
            chart(page,"Occupation summary · right-click to drill through","Occupation summary","Select an occupation to open its monthly and geographic detail.",
                  "tableEx",(682,371,691,304),{"Values":["Occupation and NOC","Location records","Advertised openings","Average hourly midpoint"]},(730,275),
                  descending("Location records"),aliases={"Occupation and NOC":"Occupation / NOC","Location records":"Records","Advertised openings":"Openings","Average hourly midpoint":"Mean CAD/h"})
            textbox(page,"Source note","Source identifies how the posting reached Job Bank.",(65,684,580,31),10,colour=SECONDARY)
            button(page,"Open occupation detail","Open occupation detail  →",(685,680,215,38),
                   {"type":"Drillthrough","drillthroughSection":key(DETAIL),"disabledTooltip":"Select one occupation in the table."},secondary=True,mobile=(5,1010,308,44))
        elif name=="Demand Over Time":
            series=["Location records","Advertised openings"]
            style=fmt(showMarker=True,strokeWidth=3)+[state({"lineStyle":sty,"markerShape":mark,"showMarker":True,"strokeColor":cl},
                    {"metadata":"Postings."+n}) for n,sty,mark,cl in zip(series,("solid","dashed"),("circle","square"),(GREEN,BLUE))]
            chart(page,"Monthly job demand · location records and openings","Monthly job demand","Posting locations and advertised openings",
                  "lineChart",(63,371,677,313),{"Category":["Month"],"Y":series},(785,245),("Month","Ascending"),
                  {"lineStyles":style,"dataPoint":[measure_colour(n,cl) for n,cl in zip(series,(GREEN,BLUE))]},aliases={"Location records":"Posting locations"})
            chart(page,"Top 10 occupations · posting locations","Top 10 occupations","Ranked by posting locations",
                  "clusteredBarChart",(776,371,600,319),roles("Occupation and NOC","Top occupation records",["Advertised openings"]),(475,302),
                  descending("Top occupation records"),ranked="Top occupation records")
            textbox(page,"Demand units","Each record is one posting location. A record can advertise several openings.",(64,690,680,28),10,colour=SECONDARY)
        elif name=="Geographic Distribution":
            geo={"geoJson":{"type":string("shared"),"name":string("canada.provinces.topo"),"content":{"expr":{
                 "ResourcePackageItem":{"PackageName":"SharedResources","PackageType":2,"ItemName":"canada.provinces.topo"}}}}}
            chart(page,"Canada · postings by province or territory","Posting locations across Canada","First-posting records by province or territory",
                  "shapeMap",(63,254,654,385),{"Category":["Map province"],"Value":["Location records"],"Tooltips":["Advertised openings"]},(232,285),
                  extra={"shape":prop(map=geo,projectionEnum=string("orthographic")),"legend":fmt(show=False),
                         "dataPoint":[{"selector":{"data":[{"dataViewWildcard":{"matchingOption":1}}]},
                              "properties":{"fill":{"solid":{"color":{"expr":field("Province count colour")}}}}}]})
            textbox(page,"Province scale","Posting locations",(64,631,315,36),10,colour=SECONDARY)
            for index,label in enumerate(("<1k","1k–<5k","5k–<10k","10k–<25k","25k–<40k","40k+")):
                textbox(page,"Map band "+str(index),label,(64+index*105,673,103,37),9,colour=SECONDARY)
            for prefix,category,identifier,caption,subtitle,top,phone_top,colour in [
                    ("Province","Province","Postings by province or territory","By province or territory","Posting locations, ranked nationally",252,528,GREEN),
                    ("City","City and province","Top 10 cities · posting locations","Top 10 cities","Ranked by posting locations",473,976,BLUE)]:
                textbox(page,prefix+" ranking heading",caption,(756,top-9,615,39),16,weight=True)
                textbox(page,prefix+" ranking caption",subtitle,(756,top+25,616,36),10,colour=SECONDARY)
                for j,part in enumerate(("leading","remaining")):
                    metric=prefix+" "+part+" records"
                    properties={"dataPoint":fmt(defaultColor=colour),
                                "labels":fmt(show=True,fontSize=9,fontFamily=FONT,color=INK,labelDisplayUnits=1,labelPosition="OutsideEnd"),
                                "categoryAxis":fmt(showAxisTitle=False,maxMarginFactor=52,preferredCategoryWidth=16,
                                                   innerPadding=35,fontSize=9,labelColor=SECONDARY),
                                "valueAxis":fmt(show=False,showAxisTitle=False,start=0,end={"expr":field(prefix+" scale maximum")})}
                    chart(page,identifier if j==0 else identifier+" continued",None,None,
                          "clusteredBarChart",(760+j*310,top+51,307,167 if prefix=="Province" else 187),
                          roles(category,metric,[prefix+" "+part+" openings"]),(phone_top+j*222,217),descending(metric),properties,
                          aliases={metric:"Posting locations",prefix+" "+part+" openings":"Advertised openings"},
                          mobile_caption=caption+(" (continued)" if j else ""))
        elif name=="Qualifications":
            chart(page,"Education requirements by occupation · posting locations","Education by occupation","Stacked counts for each occupation and NOC",
                  "barChart",(62,253,646,284),{"Category":["Occupation and NOC"],"Series":["Education label"],"Y":["Location records"]},(232,355),
                  descending("Location records"),{"legend":fmt(show=False),
                      "dataPoint":[data_colour("Education label",label,cl) for raw,label,cl in EDUCATION_STYLES]})
            chart(page,"Education legend",None,None,"tableEx",(62,544,645,165),{"Values":["Education colour key"]},(1183,148),
                  extra={"grid":fmt(imageHeight=102,imageWidth=600,gridHorizontal=False,gridVertical=False,rowPadding=1),
                         "total":fmt(totals=False)},aliases={"Education colour key":"Education level"})
            chart(page,"Experience requirements · posting locations","Experience requirements","Posting locations across all experience responses",
                  "clusteredBarChart",(744,254,630,233),roles("Experience","Location records"),(596,265),descending("Location records"),
                  {"dataPoint":fmt(defaultColor=GREEN)+[data_colour("Experience","Not recorded",MISSING)]})
            chart(page,"Occupation and qualification comparison","Occupation and qualification comparison","Posting locations by recorded response",
                  "tableEx",(744,496,630,215),{"Values":["Occupation and NOC","Education","Experience","Location records"]},(868,300),
                  descending("Location records"),aliases={"Occupation and NOC":"Occupation / NOC","Location records":"Records"})
        elif name=="Compensation":
            chart(page,"Average pay · CAD/hour · 10 occupations with most hourly records","Average pay by occupation",
                  "Ten occupations with the most hourly records, ordered by average midpoint.","clusteredBarChart",(62,371,634,317),
                  roles("Occupation and NOC","Hourly pay in leading occupations",["Hourly records","Average hourly lower","Average hourly upper"]),(475,310),
                  descending("Hourly pay in leading occupations"),ranked="Hourly pay in leading occupations")
            chart(page,"Average range by province · CAD/hour · marker is midpoint","Hourly pay ranges by province",
                  "Line spans mean lower to upper bound. The dot marks the mean midpoint.","tableEx",(734,371,646,327),
                  {"Values":["Province","Hourly range graphic","Average hourly lower","Average hourly upper","Average hourly midpoint"]},(795,350),
                  descending("Average hourly midpoint"),aliases={"Hourly range graphic":"Range","Average hourly lower":"Lower","Average hourly upper":"Upper","Average hourly midpoint":"Midpoint"})
            textbox(page,"Hourly pay note","Extreme advertised amounts can raise the mean. All pay is in CAD per hour.",(62,691,690,31),10,colour=SECONDARY)
        elif name=="Work Conditions":
            chart(page,"Employment type · posting locations","Employment type","Share of all selected posting locations",
                  "donutChart",(62,251,390,305),roles("Employment type","Location records"),(232,270),
                  extra={"legend":fmt(show=False),"labels":fmt(show=False),"dataPoint":[data_colour("Employment type",t,cl) for t,cl in
                      [("Full time",GREEN),("Part time",BLUE),("Not recorded",MISSING),("Part time leading to full time","#956727")]]})
            visual(page,"Full time percentage","card",(191,393,128,68),{"Values":["Full-time share"]},caption="Full time",
                   container={"title":fmt(show=True,text="Full time",alignment="center",fontSize=10,fontColor=SECONDARY)},
                   objs={"categoryLabels":fmt(show=False),"labels":fmt(fontSize=20,color=INK)},mobile=(5,510,308,70))
            chart(page,"Employment type counts",None,None,"tableEx",(62,558,390,151),
                  {"Values":["Employment type","Location records"]},(1391,202),descending("Location records"),
                  extra={"total":fmt(totals=False)},aliases={"Location records":"Records"})
            chart(page,"Weekly hours · midpoint of reported range","Weekly hours","Midpoint of each reported weekly range",
                  "clusteredColumnChart",(482,252,407,444),roles("Weekly hours band","Location records"),(588,270),("Weekly hours band","Ascending"),
                  {"dataPoint":fmt(defaultColor=GREEN)+[data_colour("Weekly hours band","Not recorded",MISSING)]})
            colours=[measure_colour(n,cl) for n,cl in zip(("Yes","No","Not recorded"),(GREEN,BLUE,MISSING))]
            chart(page,"Work arrangements and benefits · records","Arrangements & benefits","Response counts for each work condition",
                  "barChart",(918,252,460,238),{"Category":["Indicator"],"Y":["Yes","No","Not recorded"]},(869,255),extra={"dataPoint":colours})
            chart(page,"Response counts","Response counts",None,"tableEx",(918,503,460,202),
                  {"Values":["Indicator","Displayed Yes","Displayed No","Displayed Not recorded"]},(1134,245),
                  extra={"total":fmt(totals=False)},aliases={"Displayed "+n:n for n in ("Yes","No","Not recorded")})
        else:
            button(page,"Back to selection","←   Back to selection",(1190,77,204,44),{"type":"Back"},secondary=True,mobile=(5,231,308,44))
            visual(page,"Selected occupation","card",(65,251,610,44),{"Values":["Occupation detail heading"]},
                   objs={"categoryLabels":fmt(show=False),"labels":fmt(fontSize=15,color=GREEN)},mobile=(5,281,308,52))
            chart(page,"Occupation by month","Occupation by month","Comparable hourly ranges and advertised openings","tableEx",
                  (62,302,616,385),{"Values":["Occupation and NOC","Month","Location records","Advertised openings","Hourly records","Median hourly midpoint"]},
                  (342,259),("Month","Ascending"),aliases={"Occupation and NOC":"Occupation / NOC","Location records":"Records","Advertised openings":"Openings","Median hourly midpoint":"Median CAD/h"})
            chart(page,"Locations within province and economic region","Locations within economic regions","Posting locations and advertised openings",
                  "tableEx",(712,253,667,444),{"Values":["City","Economic region","Province","Location records","Advertised openings"]},
                  (610,395),descending("Location records"),aliases={"Location records":"Records","Advertised openings":"Openings"})
def build():
    schema(DEST/"Job Bank.pbip","pbip/pbipProperties/1.0.0",version="1.0",artifacts=[{"report":{"path":REPORT.name}}],settings={"enableAutoRecovery":True})
    schema(REPORT/"definition.pbir","item/report/definitionProperties/2.0.0",version="4.0",datasetReference={"byPath":{"path":"../"+MODEL.name}})
    schema(MODEL/"definition.pbism","item/semanticModel/definitionProperties/1.0.0",version="1.0",settings={})
    write(MODEL/"model.bim",build_model(HOST,PORT,DATABASE))
    schema(DEF/"version.json",RS+"versionMetadata/1.0.0",version="2.0.0")
    nv={"visual":"2.1.0","report":"3.0.0","page":"2.0.0"}
    theme={"name":"Job Bank Studio","dataColors":[GREEN,BLUE,"#98672F","#735899","#4F8759","#A65B70",
           "#247F9D","#977D3D","#445B82","#A56A45","#58695A",MISSING],
           "background":WHITE,"foreground":INK,"foregroundNeutralSecondary":SECONDARY,"tableAccent":GREEN,
           "minimum":"#DAE9E1","center":"#67AE99","maximum":"#164C47","null":MISSING,
           "textClasses":{c:{"fontFace":FONT,"color":INK} for c in ("title","header","label","callout")}}
    write(REPORT/"StaticResources/RegisteredResources/D42Blueprint.json",theme)
    schema(DEF/"report.json",RS+"report/3.0.0",themeCollection={
        "baseTheme":{"name":"CY24SU10","type":"SharedResources","reportVersionAtImport":nv},
        "customTheme":{"name":"D42Blueprint","type":"RegisteredResources","reportVersionAtImport":nv}},
        resourcePackages=[{"name":"SharedResources","type":"SharedResources","items":[
            {"name":"CY24SU10","path":"BaseThemes/CY24SU10.json","type":"BaseTheme"},
            {"name":"canada.provinces.topo","path":"Shapemaps/canada.provinces.topo.json","type":"ShapeMap"}]},
            {"name":"RegisteredResources","type":"RegisteredResources","items":[
            {"name":"D42Blueprint","path":"D42Blueprint.json","type":"CustomTheme"}]+[
                {"name":f"Layout{i}.png","path":f"Layout{i}.png","type":"Image"} for i in range(len(PAGES)+1)]}])
    all_pages()
    schema(DEF/"pages/pages.json",RS+"pagesMetadata/1.0.0",pageOrder=[key(x) for x in PAGES+[DETAIL]],activePageName=key("Overview"))
if __name__=="__main__":
    build()
    print("Wrote the Job Bank desktop and phone report layouts.")
