# load up the libraries
import panel as pn
import matplotlib.pyplot as plt
import ipywidgets as widgets
import pandas as pd
import altair as alt
from altair_transform import extract_data
import Robogame as rg
import time,json
import networkx as nx
import traceback
from collections import defaultdict
import pprint
import seaborn as sns
import warnings
import math
warnings.simplefilter(action='ignore', category=FutureWarning)

# we want to use bootstrap/template, tell Panel to load up what we need
pn.extension(design='bootstrap')
pn.extension('vega')
pn.extension('ipywidgets')

# load up the data
def getFrame():
    # load up the two datasets, one for Marvel and one for DC    
    return(pd.DataFrame())

default_username = "bob"
default_server = "127.0.0.1"
default_port = "5000"

username_input= pn.widgets.TextInput(name='Username:', placeholder=default_username)
servername_input= pn.widgets.TextInput(name='Server', placeholder='127.0.0.1')
port_input= pn.widgets.TextInput(name='Port', placeholder='5000')
go_button = pn.widgets.Button(name='Run', button_type='primary')
static_text = pn.widgets.StaticText(name='State', value='Hit go to start')

sidecol = pn.Column()
sidecol.append(static_text)
sidecol.append(username_input)
sidecol.append(servername_input)
sidecol.append(port_input)
sidecol.append(go_button)


network = None
tree = None
info = None
hints = None
predDict = None

game = None

previousBets = {}

predIdKey = "id"
predTimeKey = "time"
predValueKey = "value"
columnKey = "column"
idKey = "id"
valueKey = "value"
productivityCol = "Productivity"

nextExpiry = -1

all_numeric_cols = ['InfoCore Size', 'AutoTerrain Tread Count', 'Repulsorlift Motor HP', 'Astrogation Buffer Length',
                'Polarity Sinks', 'Cranial Uplink Bandwidth', 'Sonoreceptors', "Productivity"]
all_category_cols = ['Axial Piston Model','Arakyd Vocabulator Model','Nanochip Model']
nominalVars = ['Axial Piston Model','Arakyd Vocabulator Model','Nanochip Model']

def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3

def getNumericAndCategoryCols(dfDict):
    global all_numeric_cols, all_category_cols
    
    curr_columns = list(dfDict.keys())

    numeric = intersection(all_numeric_cols, curr_columns)
    category = intersection(all_category_cols, curr_columns)
    return numeric, category


# def getProductivityPlot(df, selected_column):
#     global nominalVars, productivityPlot
#     plt.figure()
    
#     plt.scatter(df[selected_column], df[productivityCol])
#     if selected_column not in nominalVars:
#       sns.regplot(x=df[selected_column], y=df[productivityCol])

#     plt.xlabel(selected_column)
#     plt.ylabel(productivityCol)
#     plt.title(f'Scatter Plot of {selected_column} vs Productivity')
    
#     figure = plt.gcf()
#     plt.show()
#     productivityPlot.object = figure
    

def updateParts(allParts, robotDf):
    global partsInfoObject, info_test, productivityPlot
    
    partsInfoDict = defaultdict(dict)
    
    nonNanProductivity = robotDf[~robotDf[productivityCol].isna()][productivityCol]
    robotIds = nonNanProductivity.index
    robotProductivity = list(nonNanProductivity)
    for i, id in enumerate(robotIds):
        partsInfoDict[productivityCol][id] = robotProductivity[i]
    
    # print(nonNanProductivity)
    
    # print(allParts, "\n\n\n")
    
    for parts in allParts:
        column = parts[columnKey]
        id = parts[idKey]
        value = parts[valueKey]
        partsInfoDict[column][id] = value
    
    # print(partsInfoDict, "\n\n\n")
    
    partsInfoDf = pd.DataFrame.from_dict(partsInfoDict)
    numeric_cols, category_cols = getNumericAndCategoryCols(partsInfoDict)
    
    partsInfoDf[numeric_cols] = partsInfoDf[numeric_cols].apply(pd.to_numeric, errors='coerce')
    partsInfoDf[category_cols] = partsInfoDf[category_cols].astype('category')
    
    correlation_matrix = partsInfoDf[numeric_cols].corr()
    correlation_melted = pd.melt(correlation_matrix.reset_index(), id_vars='index')

    # Rename the columns
    correlation_melted.columns = ['Variable 1', 'Variable 2', 'Correlation']

    # Create the heatmap using Altair
    correlationPlot = alt.Chart(correlation_melted).mark_rect().encode(
        x='Variable 1:N',
        y='Variable 2:N',
        color='Correlation:Q'
    ).properties(
        title='Correlation Heatmap'
    )
    
    partsInfoObject.object = correlationPlot
    

def update():
    try:
        global game, static_text, tree_view, info_view, hints_view, predDict, robo_expiry_sorted
        robo_expiry_sorted.object = getRoboSorted()
        gt = game.getGameTime()
        # network_view.object = game.getNetwork()
        tree_view.object = game.getTree()
        robotDf = game.getRobotInfo()
        info_view.object = robotDf
        hints_view.object = game.getHints(hintstart=0)
        allPred = game.getAllPredictionHints()
        allParts = game.getAllPartHints()
        
        updateParts(allParts, robotDf)
        drawProductivityPlots()
        
        predDict = defaultdict(lambda: defaultdict(list))
        for pred in allPred:
            roboId = pred[predIdKey]
            predTime = pred[predTimeKey]
            value = pred[predValueKey]
            predDict[roboId][predTimeKey].append(predTime)
            predDict[roboId][predValueKey].append(value)
        
        hints_view.object = predDict
        robo_time_chart.object = getTimeChart()
        
        global nextExpiry
        # print("\n\n\n\n", nextExpiry, "\n\n\n\n")
        curr_time = 100 - gt['unitsleft']
        # if curr_time > nextExpiry:
        #     combined_sort_time_chart.object = combined_sort_time()
            
        static_text.value = f"Current time: {curr_time}"
    except:
        print(traceback.format_exc())

def go_clicked(event):
    try:
        global game, network, tree, info, hints, robo_expiry_sorted
        go_button.disabled = True
        uname = username_input.value
        if (uname == ""):
            uname = default_username
        server = servername_input.value
        if (server == ""):
            server = default_server
        port = port_input.value
        if (port == ""):
            port = default_port

        print(uname, server, port)
        game = rg.Robogame(uname,server=server,port=int(port))
        readResp = game.setReady()
        # if ('Error' in readResp):
        #     static_text.value = "Error: "+str(readResp)
        #     go_button.disabled = False
        #     return
        

        while(True):
            gametime = game.getGameTime()
            
            if ('Error' in gametime):
                if (gametime['Error'] == 'Game not started'):
                    static_text.value = "Game not started yet, waiting"
                    time.sleep(1)
                    continue
                else:
                    static_text.value = "Error: "+str(gametime)
                    break

            timetogo = gametime['gamestarttime_secs'] - gametime['servertime_secs']
            if (timetogo <= 0):
                static_text.value = "Let's go!"
                break
            static_text.value = "waiting to launch... game will start in " + str(int(timetogo))
            time.sleep(1) # sleep 1 second at a time, wait for the game to start

        # run a check every 5 seconds
        robo_expiry_sorted.object = getRoboSorted()
        cb = pn.state.add_periodic_callback(update, 6000, timeout=600000)
    except:
        #print(traceback.format_exc())
        return

go_button.on_click(go_clicked)

template = pn.template.BootstrapTemplate(
    title='Robogames Demo',
    sidebar=sidecol,
)

# #clickable sorted robo+time series
# def combined_sort_time():
#     #prepare data
#     global game
#     if game is None:
#         return None
#     robots = game.getRobotInfo()
#     network = game.getNetwork()
#     socialnet = nx.node_link_graph(network)
#     robotDegrees = {node:val for (node, val) in socialnet.degree()}
#     robotRecords = robots.to_dict("records")
#     sortedRobotRecords = sorted(robotRecords, key=lambda x:x["expires"])
    
#     gt = game.getGameTime()
#     currTime = 100 - gt['unitsleft']
    
#     filteredRobotRecords = getFilteredRobotRecords(sortedRobotRecords, robotDegrees, currTime=currTime)
    
#     global nextExpiry
#     nextExpiry = filteredRobotRecords[0]["expires"]
    
#     robotDfWithRank = pd.DataFrame.from_records(filteredRobotRecords)

#     print('-------------')
#     print('data1 loaded')

#     global predDict
#     if predDict is None:
#         return None
#     all_robo_df = pd.DataFrame(columns=['id', 'data'])

#     # Loop through the data_dict and collect data for concatenation
#     data_frames = []  # List to hold data frames for concatenation
#     for key, value in predDict.items():
#         if isinstance(key, int):
#             temp_df = pd.DataFrame({'id': [key], 'data': [value]})
#             data_frames.append(temp_df)

#     # Concatenate all data frames
#     all_robo_df = pd.concat(data_frames, ignore_index=True)

#     print('---------------')
#     print('data2-1 loaded')

#     data = all_robo_df
#     df = pd.DataFrame(data)

#     new_data = []
#     for index, row in df.iterrows():
#         id_value = row['id']
#         data_dict = row['data']
        
#         if isinstance(data_dict, dict):  # Check if 'data' is a dictionary
#             time_values = data_dict.get('time', [])
#             value_values = data_dict.get('value', [])
            
#             if not time_values and not value_values:  # Check if both 'time' and 'value' are empty
#                 new_data.append({'id': id_value, 'time': None, 'value': None})
#             else:
#                 for time, value in zip(time_values, value_values):
#                     new_data.append({'id': id_value, 'time': time, 'value': value})
#         else:
#             new_data.append({'id': id_value, 'time': None, 'value': None})

#     new_df = pd.DataFrame(new_data)
#     all_robo_df = new_df


#     print('---------------')
#     print('data2 loaded')

#     # Define a selection in the first chart (similar to the previous example)

#     # selection = alt.selection_single(fields=['id'],on = 'click', empty = 'none', name="brush")

#     chart_width = 400
#     chart_height = 300

#     robo_expiry_sorted = alt.Chart(robotDfWithRank).mark_circle(size=100).encode(
#         alt.X('rank',  axis=alt.Axis(labels=False) ),
#         size=alt.Size('degree:Q', legend=alt.Legend(symbolLimit=4)),
#         color=alt.condition(selection, alt.value('red'), alt.value('steelblue')),
#         tooltip=['name', 'expires', 'rank', "id", "degree"]
#     ).properties(
#         width=800
#     )
#     # .add_selection(
#     #     selection
#     # )
    
#     text = alt.Chart(robotDfWithRank).mark_text(
#         align='left',
#         baseline='middle',
#         dx=10,
#         fontSize=10
#     ).encode(
#         alt.X('rank',  axis=alt.Axis(labels=False) ),
#         text='id',
#         # color=alt.condition(selection, alt.value('red'), alt.value('steelblue')),
#     )
#     # .add_selection(
#     #     selection
#     # )
    
#     robo_expiry_sorted = robo_expiry_sorted + text
    
#     currRobotDf = all_robo_df.loc[all_robo_df['id'] == 5]


#     # Use the selection to filter data for the second chart
#     robo_time_chart = alt.Chart(currRobotDf).mark_circle(color="red").encode(
#         x=alt.X('time:Q', scale=alt.Scale(domain=[0, 100])),
#         y=alt.Y('value:Q', scale=alt.Scale(domain=[0, 100])),
#         # tooltip=['time', 'value']
#     ).properties(
#         width=chart_width,
#         height=chart_height
#     )


#     # Add line and expiry line to the second chart
#     line = alt.Chart(currRobotDf).mark_line(interpolate="monotone").encode(
#         x=alt.X('time:Q',  scale=alt.Scale(domain=[0, 100])),  # Assuming 'time' is a categorical variable
#         y=alt.Y('value:Q', scale=alt.Scale(domain=[0, 100]))  # Assuming 'value' is a quantitative variable
#     )
#     # ).transform_filter(
#     #     selection  # Apply the selection filter here
#     # )
#     currRobotDfWithRank = robotDfWithRank.loc[robotDfWithRank['id'] == 5]
#     expiryLine = alt.Chart(currRobotDfWithRank).mark_rule(color='black').encode(
#         x=alt.X('expires:Q', scale=alt.Scale(domain=[0, 100]) ) # Adjust the encoding to use the 'expires' field
#     )
#     # .transform_filter(
#     #     selection  # Filter based on the selected 'id'
#     # )


#     # Combine the line, points, and expiry line
#     combined_chart = line + robo_time_chart + expiryLine
   
#     # Display the charts
#     final_chart = alt.vconcat(  robo_expiry_sorted, combined_chart)

#     return final_chart



def getTimeChart():
    global curr_selected_robot, predDict
    # print(f"\n\n\n textInput = {textInput} \n\n\n")
    
    robotId = curr_selected_robot
        
    global predDict
    if predDict is None:
        return None
    if robotId not in predDict:
        robotInfo = game.getRobotInfo()
        emptyChart = alt.Chart().mark_point().encode(
            x=alt.X('time:Q', scale=alt.Scale(domain=[0, 100])),
            y=alt.Y('value:Q', scale=alt.Scale(domain=[0, 100])),
        ).properties(
            width=400,
            height=300
        )
        if robotId < 0 or robotId > 100:
            return emptyChart
        
        robotInfo = game.getRobotInfo()
        currRobot = robotInfo[robotInfo['id'] == robotId]
        expiry = currRobot["expires"].iloc[0]
        expiryLine = alt.Chart(pd.DataFrame({"x": [expiry]})).mark_rule().encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[0, 100])),
        ).properties(
            title=f"Robot {robotId}'s data",
            width=400,
            height=300
        )
        return emptyChart + expiryLine

    
    robo_df = pd.DataFrame.from_dict(predDict[robotId])
    points = alt.Chart(robo_df).mark_circle(color="red").encode(
        x=alt.X('time:Q', scale=alt.Scale(domain=[0, 100])),
        y=alt.Y('value:Q', scale=alt.Scale(domain=[0, 100])),
        tooltip=['time', 'value']
    ).properties(
        title=f"Robot {robotId}'s data",
        width=400,
        height=300
    )

    line = alt.Chart(robo_df).mark_line(interpolate="monotone").encode(
        x='time:Q',
        y='value:Q'
    )

    robotInfo = game.getRobotInfo()
    currRobot = robotInfo[robotInfo['id'] == robotId]
    expiry = currRobot["expires"].iloc[0]
    expiryLine = alt.Chart(pd.DataFrame({"x": [expiry]})).mark_rule().encode(
        x="x:Q"
    )

    return line + points + expiryLine

def getRoboSorted():
    global game, curr_selected_robot
    if game is None:
        return None
    robots = game.getRobotInfo()
    network = game.getNetwork()
    socialnet = nx.node_link_graph(network)
    robotDegrees = {node:val for (node, val) in socialnet.degree()}
    robotRecords = robots.to_dict("records")
    sortedRobotRecords = sorted(robotRecords, key=lambda x:x["expires"])
    
    gt = game.getGameTime()
    # print(gt)
    currTime = 100 - gt['unitsleft']
    
    tree = game.getTree()
    genealogy = nx.tree_graph(tree)
    
    filteredRobotRecords = getFilteredRobotRecords(sortedRobotRecords, robotDegrees, genealogy, robotRecords, currTime=currTime)
    
    robotDfWithRank = pd.DataFrame.from_records(filteredRobotRecords)
    timeSeries = alt.Chart(robotDfWithRank).mark_circle(size=100).encode(
        alt.X('rank', axis=None),
        size=alt.Size('degree:Q', legend=None),
        tooltip=['name', 'expires', 'rank', "id", "degree", "productivity"],
        # color=alt.condition(alt.datum.id == curr_selected_robot, alt.value('red'), alt.value('steelblue')),
        color=alt.Color("productivity:Q", scale=alt.Scale(
            domain=[-100, 0, 100],
            range=['red', "white", 'blue']
        )
    )).properties(
        width=800
    )
    
    text = alt.Chart(robotDfWithRank).mark_text(
        align='left',
        baseline='middle',
        dx=10,
        fontSize=10
    ).encode(
        alt.X('rank',  axis=alt.Axis(labels=False) ),
        text='id',
    )
    
    return timeSeries + text

def updatePreviousBets():
    global previousBets, previousBetsText, curr_selected_robot
    print(previousBets)
    if curr_selected_robot not in previousBets:
        previousBetsText.value = ""
        print("returning empty")
        return
    print(previousBets[curr_selected_robot])
    previousBetsText.value = ', '.join(str(x) for x in previousBets[curr_selected_robot])
    
    

def updateCurrSelected(textInput):
    global curr_selected_robot, robo_time_chart, predDict
    if predDict is None:
        return None
    try:
        curr_selected_robot = int(textInput)
        robo_time_chart.object = getTimeChart()
        robo_expiry_sorted.object = getRoboSorted()
        getRobotParts()
        print("updating previous bets")
        updatePreviousBets()
        return pn.pane.Alert("Updated!", alert_type="success")
    except Exception as e:
        return pn.pane.Alert(str(e), alert_type="danger")

def getAverageProductivity(neighbors, roboDict):
    total = 0
    count = 0
    for neighborId in neighbors:
        productivity = roboDict[neighborId]["Productivity"]
        if productivity is None or math.isnan(productivity):
            continue
        total += productivity
        count += 1
            
    if count == 0:
        return 0
    return total / count
    

def getFilteredRobotRecords(sortedRobotRecords, robotDegrees, network, roboDict, currTime = 20, numCount = 20):
    filteredRobotRecords = []
    currRank = 1
    currCount = 0
    for robot in sortedRobotRecords:
        if robot["id"] >= 100:
            break
        if robot["expires"] < currTime:
            continue
        robot["rank"] = currRank
        robot["degree"] = robotDegrees[robot["id"]]
        
        
        neighbors = nx.all_neighbors(network, robot["id"])
        twoDistAway = set()
        for neighbor in neighbors:
            twoDist = nx.all_neighbors(network, neighbor)
            for node in twoDist:
                twoDistAway.add(node)
                
                
        robot['productivity'] = getAverageProductivity(twoDistAway, roboDict)
        currRank += 1
        filteredRobotRecords.append(robot)
        currCount += 1
        if currCount >= numCount:
            break
        
    return filteredRobotRecords

def sendRobotRequest(textInput):
    global curr_selected_robot, predDict, previousBets
    if predDict is None:
        return None
    
    if curr_selected_robot == -1:
        return pn.pane.Alert("current robot not selected", alert_type="danger")
    try:
        betVal = int(textInput)
        apiParam = {curr_selected_robot: betVal}
        
        if curr_selected_robot not in previousBets:
            previousBets[curr_selected_robot] = []
        previousBets[curr_selected_robot].append(betVal)
        
        # for robot in robots:
        #     robotId, guessVal = robot.split(":")
        #     robotId, guessVal = int(robotId), int(guessVal)
        #     print(f"{robotId}:{guessVal}")
        #     apiParam[robotId] = guessVal
            
        game.setBets(apiParam)
        updatePreviousBets()
        return pn.pane.Alert("Updated!", alert_type="success")
    except Exception as e:
        return pn.pane.Alert(str(e), alert_type="danger")

def setCurrRobotBetMessage():
    global robotBetMessage
    robotBetMessage.object = f"Robot {curr_selected_robot}'s guess: "
    
def getRobotParts():
    global roboParts, curr_selected_robot
    allParts = game.getAllPartHints()
    allPartsDf = pd.DataFrame(allParts)
    currRobotPartsDf = allPartsDf.loc[allPartsDf['id'] == curr_selected_robot].drop(columns=["id"])
    currRobotPartsDf = currRobotPartsDf.rename(columns={"column": "feature"})
    currRobotPartsDf = currRobotPartsDf.sort_values(by=['feature'])
    roboParts.object = currRobotPartsDf

partNames = ['InfoCore Size', 'AutoTerrain Tread Count', 'Repulsorlift Motor HP', 'Astrogation Buffer Length',
             
                'Polarity Sinks', 'Cranial Uplink Bandwidth', 'Sonoreceptors']
partNames.sort()
partsIsChecked = {partName: True for partName in partNames}
partsProductivityPlot = {partName: pn.pane.Vega(None) for partName in partNames}

def updatePartsCheck(partName):
    global partsIsChecked
    partsIsChecked[partName] = not partsIsChecked[partName]
    drawProductivityPlots()
    
def drawProductivityPlots():
    global game, partNames, partsIsChecked, partsProductivityPlot
    if game is None:
        return
    partsInfoDict = defaultdict(dict)
    allParts = game.getAllPartHints()
    robotDf = game.getRobotInfo()
    
    nonNanProductivity = robotDf[~robotDf[productivityCol].isna()][productivityCol]
    robotIds = nonNanProductivity.index
    robotProductivity = list(nonNanProductivity)
    for i, id in enumerate(robotIds):
        partsInfoDict[productivityCol][id] = robotProductivity[i]
    if len(partsInfoDict[productivityCol]) == 0:
        return
    
    for parts in allParts:
        column = parts[columnKey]
        id = parts[idKey]
        value = parts[valueKey]
        partsInfoDict[column][id] = value
    
    # print(partsInfoDict, "\n\n\n")
    
    partsInfoDf = pd.DataFrame.from_dict(partsInfoDict)
    
    for partName in partNames:
        # print(f"{partName} checked val is {partsIsChecked[partName]}")
        if not partsIsChecked[partName]:
            partsProductivityPlot[partName].object = None
        
        partsProductivityPlot[partName].object = drawProductivityPlotPerPart(partsInfoDf, partName)
        
def drawProductivityPlotPerPart(partsInfoDf, partName):
    fig = alt.Chart(partsInfoDf).mark_point(filled=True).encode(
        y=f'{productivityCol}:Q',
        x=f'{partName}:Q',
        tooltip=['Productivity', f'{partName}']
    ).properties(
        title=f'Plot for {partName}',
        width=100,
        height=100,
    )
    
    return fig + fig.transform_regression(partName, productivityCol).mark_line() 

def requestInterestedRobots(input):
    global previousBets
    if game is None:
        return
    try:
        defaultBets = {}
        robotList = []
        for roboId in input.split(","):
            intId = int(roboId)
            if intId not in previousBets:
                defaultBets[intId] = 50
                previousBets[intId] = [50]
            
            robotList.append(intId)
        game.setBets(defaultBets)
        game.setRobotInterest(robotList)
        return pn.pane.Alert("Updated!", alert_type="success")
    except Exception as e:
        return pn.pane.Alert(str(e), alert_type="danger")

# network_view = pn.pane.JSON({"message":"network waiting for game to start"})
partsInfoObject = pn.pane.Vega(None)
tree_view = pn.pane.JSON({"message":"treeview waiting for game to start"})
info_view = pn.pane.DataFrame()
roboParts = pn.pane.DataFrame()
hints_view = pn.pane.JSON({"message":"hints waiting for game to start"})
robo_time_chart = pn.pane.Vega(None)
robo_expiry_sorted = pn.pane.Vega(None)
curr_selected_robot = -1
productivityPlot = pn.pane.Matplotlib(None)
robotBetMessage = pn.pane.Alert(None)
setCurrRobotBetMessage()
# combined_sort_time_chart = pn.pane.Vega(None)

maincol = pn.Column()

# robotIdInput = pn.widgets.TextInput(placeholder="Robot ID")

# rowChart = pn.Row(pn.bind(updateCurrSelected, robotIdInput))

betRobotId = pn.widgets.TextInput(placeholder="Interested Robot ID in format id1: guess1, id2: guess2")
showRobot = pn.widgets.TextInput(placeholder="Robot ID to display below")
placeBet = pn.widgets.TextInput(placeholder="Robot's value guess here")

robotRequestRow = pn.Row(betRobotId, pn.bind(requestInterestedRobots, betRobotId))
setRobotIdToShow = pn.Row(showRobot, pn.bind(updateCurrSelected, showRobot))
robotBetRow = pn.Row(placeBet)
betResult = pn.bind(sendRobotRequest, placeBet)


# grid = pn.GridBox(ncols=2,nrows=3)
# grid.append(network_view)
# grid.append(productivityPlot)
# grid.append(info_view)
# grid.append(partsInfoObject)
# grid.append(tree_view)
# grid.append(info_view)
# grid.append(hints_view)


# timechart = getTimeChart(3)
maincol.append(robo_time_chart)

# maincol.append(rowChart)
# maincol.append(robotIdInput)

maincol.append(robotRequestRow)
maincol.append(setRobotIdToShow)
# maincol.append(betRobotId)

maincol.append("Upcoming robots and its popularity in the social network:")
maincol.append(robo_expiry_sorted)
# maincol.append(combined_sort_time_chart)
previousBetsText = pn.widgets.StaticText(name='Previous Bets', value='Previous Bets')

selectedRobotGrid = pn.GridSpec(ncols=3,nrows=15, width=1000, height=450)
selectedRobotGrid[0:3, :] = robo_expiry_sorted
selectedRobotGrid[3:, 0:2] = robo_time_chart
selectedRobotGrid[3, 2] = robotBetRow
selectedRobotGrid[4, 2] = betResult
selectedRobotGrid[5:10, 2] = roboParts
selectedRobotGrid[10:, 2] = previousBetsText
maincol.append(selectedRobotGrid)

sidecol.append(pn.Row(partsInfoObject))

partsInfoGrid = pn.GridSpec(ncols=len(partNames),nrows=10, width=len(partNames) * 180, height=600)
for i, partName in enumerate(partNames):
    def partFunction(x):
        # print(f"calling updatePartsCheck with {partName}")
        updatePartsCheck(partName)
    btn = pn.widgets.Button(name=partName)
    pn.bind(partFunction, btn)
    partsInfoGrid[0, i] = btn
    partsInfoGrid[1, i] = pn.bind(partFunction, btn)
    partsInfoGrid[2:, i] = partsProductivityPlot[partName]
# partsInfoGrid[0, 0:] = partsInfoObject
# partsInfoGrid[0, 1] = partsInfoObject
# partsInfoGrid[0, 2] = partsInfoObject

maincol.append(partsInfoGrid)

maincol.append(info_view)

template.main.append(maincol)



template.servable()