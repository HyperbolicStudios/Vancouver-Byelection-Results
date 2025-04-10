import os
import pandas as pd
import plotly.graph_objects as go

mapbox_access_token = os.environ['MAPBOX_KEY']

data = pd.read_csv('data.csv', skiprows=2)
locations = pd.read_csv('voting-places-2025.csv')

#drop the last row (total)
data = data.drop(data.index[-1])

#rename the first column to 'Location'
data = data.rename(columns={data.columns[0]: 'Location'})

def clean(x):
    x = x.split(' ', 1)[1].strip()
    
    if x.find("Vancouver City Hall") != -1:
        x = "Vancouver City Hall"

    return x

data.Location = data.Location.apply(clean)

data = data.groupby('Location').sum().reset_index()

#drop the following columns: Times Cast, Undervotes, Overvotes, Total Votes, Geom
data = data.drop(columns=['Times Cast', 'Undervotes', 'Overvotes', 'Total Votes'])

for column_name in data.columns[1:]:

    #if it's not a party
    if column_name.find("ABC") == -1 and column_name.find("COPE") == -1 and column_name.find("TEAM") == -1 and column_name.find("GREEN") == -1 and column_name.find("OneCity") == -1:
        #drop the column
        data = data.drop(columns=[column_name])

#rename the columns to be more readable. In the case where a party has multiple candidates/columns, rename it to be 'ABC_1', 'ABC_2', etc.
    else:
        for party in ["ABC", "COPE", "TEAM", "GREEN", "OneCity"]:
            if column_name.find(party) != -1:
                data = data.rename(columns={column_name: party + "_" + str(data.columns.tolist().index(column_name))})
                break

#ABC and TEAM ran multiple candidates. For ABC and TEAM, for each row, calculate the max
for party in ['ABC', 'TEAM']:
    #get the columns for the party
    party_columns = [col for col in data.columns if col.startswith(party)]
    
    #calculate the max for the party
    data[party + '_max'] = data[party_columns].max(axis=1)
    #drop the party columns
    data = data.drop(columns=party_columns)

#delete everything after the underscore
for column in data.columns:
    if column.find("_") != -1:
        data = data.rename(columns={column: column.split("_")[0]})

colour_schema = {
    'OneCity': 'pink',
    'COPE': 'red',
    'GREEN': '#009245',
    'ABC': '#17A7DF',
    'TEAM': 'yellow'
}

#start creating rows for charting.
#val_0 is the min of the 5 parties for each row. col_0 is the colour, based on the above schema

def get_ranked_vals(row, n):
    #input: row of data
    #output: the number of votes and party name of the party with the nth least votes. e.g. if n = 1, return the party with the least votes. if n = 2, return the party with the second fewest votes.

    row = row.drop('Location')
    row = row.sort_values(ascending=True)
    party_value = row.iloc[n-1]
    party_name = row.index[n-1]
    return party_value, party_name

for index, row in data.iterrows():
    for n in range(1,6):
        val, party = get_ranked_vals(row, n)
        colour = colour_schema[party]
        data.at[index, 'val_' + str(n)] = val
        data.at[index, 'col_' + str(n)] = colour

#adjust the values such that for val_2, val_3... van_n, is also composed of the sum of the previous values. This is for the bubble chart
for n in range(2,6):
    data['val_' + str(n)] = data['val_' + str(n)] + data['val_' + str(n-1)]

locations = locations[['Facility Name', 'Geom']].drop_duplicates()

#merge the data with locations - left on Location, right on Facility Name
data = pd.merge(data, locations, left_on='Location', right_on='Facility Name', how='left')

#split out Geom into lat and long
data[['lat', 'long']] = data['Geom'].str.split(', ', expand=True)

#set the location of Vote By Mail to be 49.292869, -123.184003 (out in the water)

data.loc[data['Location'] == '(307) Vote By Mail', 'lat'] = 49.292869
data.loc[data['Location'] == '(307) Vote By Mail', 'long'] = -123.184003

#create figure
fig = go.Figure()

for n in range(5, 0, -1):
    series = data[['Location', 'val_' + str(n), 'col_' + str(n), 'lat', 'long']]

    #add a bubble chart series to the figure. Colour the bubbles based on the col_n column.
    fig.add_trace(go.Scattermapbox(
        lat=series['lat'],
        lon=series['long'],
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=series['val_' + str(n)]/100,
            color=series['col_' + str(n)],
            opacity=.9
        ),
        name='Rank ' + str(n)
    ))

#set figure to use mapbox background

fig.update_layout(
        title = '2025 By-Election Results - Relative Party Strength',
        title_x = 0.5,
        hovermode='closest',
        mapbox=dict(
            accesstoken=mapbox_access_token,
            style = "mapbox://styles/markedwardson/clgbco9rt001z01nw5kb5p0rr",
            bearing=0,
            pitch=0,
            zoom=12),
        #centre on median of lat and long
        mapbox_center=dict(
            lat=data['lat'].astype(float).median(),
            lon=data['long'].astype(float).median()
        )
    )

#for the legend - name the series from Rank 1, 2, etc. to OneCity, COPE, TEAM, GREEN, ABC
#To be clear, while each series (Rank 1, 2, etc.) contains data from all the parties, the legend is showing the party name associated with the most votes for the first datapoint in the series - so we can cheat a bit and use that to rename the legend.
fig.data[0].name = 'OneCity'
fig.data[1].name = 'COPE'
fig.data[2].name = 'TEAM'
fig.data[3].name = 'GREEN'
fig.data[4].name = 'ABC'

#Add some notes to the bottom of the map.
text = """
1. Non-party candidates ommitted. <br>
2. Vote by Mail location is out in the water. <br>
3. Values for ABC and TEAM are the maximum value between their two candidates. <br>
"""

fig.add_annotation(
    text=text,
    showarrow=False,
    font=dict(size=12),
    align="left",
    xref="paper",
    yref="paper",
    x=1,
    y=0,
    bordercolor="black",
    borderwidth=1,
    borderpad=4,
    bgcolor="white",
    opacity=0.8
)

fig.show()