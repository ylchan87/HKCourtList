"""
A dashboard made with plotly/dash
expects file "data.sqlite" at the same path

Usage:
python dashboard.py
"""
import dataModel as dm

import plotly.graph_objs as go
import plotly.plotly as py
# Cufflinks wrapper on plotly
import cufflinks
from plotly.offline import iplot
cufflinks.go_offline()

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table

import numpy as np
import pandas as pd
from dash.dependencies import Input, Output

session = dm.init("sqlite:///data.sqlite") #init sqlAlchemy datamodel

tags = session.query(dm.Tag).order_by(dm.Tag.name_en.asc()).all()

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

lawyer_table_cols = ['Name Chi', 'Name Eng', 'Events count']
lawyer_table = dash_table.DataTable(
                    id='lawyer-table',
                    columns=[{"name": c, "id": c} for c in lawyer_table_cols],
                    # data=df.to_dict("rows"),
                    n_fixed_rows=1,
                    # row_selectable="single",
                    pagination_mode = False,
                    style_table={
                        'maxHeight': '300',
                    },
                    style_cell_conditional=[
                        {'if': {'column_id': 'Name Chi'},
                        'width': '40%'},
                        {'if': {'column_id': 'Name Eng'},
                        'width': '40%'},
                        {'if': {'column_id': 'Events count'},
                        'width': '20%'},
                    ]
                )

time_graph = dcc.Graph(
                id='time-graph',
                # figure= to be made by update_time_graph
            )

app.layout = html.Div([
    html.Label('Choose a tag:'),
    dcc.Dropdown(
        id='tags-dropdown',
        options=[
            {'label': "%s / %s" % (t.name_en, t.name_zh), 'value': t.name_en} for t in tags
        ],
        # value='Abusive language'
        value='Bankruptcy Petition'
    ),

    
    html.Div(
        [
        html.Div(
            [
                time_graph,
            ],
            # style={'width': '49%', 'display': 'inline-block','float': 'right',  'padding': '0 20'}
        ),

        html.Div(
            [
                html.Label('Lawyers dealing with this tag:'),
                lawyer_table,
       
            ],
            # style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}
        ),

        ],
        style={'width': '39%', 'display': 'inline-block',  'padding': '0 20'}
    ),

    html.Div(
        [
            dcc.Graph(
                id='lawyer-tag-graph',
                # figure= to be made by update_lawyer_tag_graph
            ),
        ],
        style={'width': '59%', 'display': 'inline-block',  'padding': '0 20'}
    ),
    # html.Label('Multi-Select Dropdown'),
    # dcc.Dropdown(
    #     options=[
    #         {'label': 'New York City', 'value': 'NYC'},
    #         {'label': u'Montréal', 'value': 'MTL'},
    #         {'label': 'San Francisco', 'value': 'SF'}
    #     ],
    #     value=['MTL', 'SF'],
    #     multi=True
    # ),

    # html.Label('Radio Items'),
    # dcc.RadioItems(
    #     options=[
    #         {'label': 'New York City', 'value': 'NYC'},
    #         {'label': u'Montréal', 'value': 'MTL'},
    #         {'label': 'San Francisco', 'value': 'SF'}
    #     ],
    #     value='MTL'
    # ),

    # html.Label('Checkboxes'),
    # dcc.Checklist(
    #     options=[
    #         {'label': 'New York City', 'value': 'NYC'},
    #         {'label': u'Montréal', 'value': 'MTL'},
    #         {'label': 'San Francisco', 'value': 'SF'}
    #     ],
    #     values=['MTL', 'SF']
    # ),

    # html.Label('Text Input'),
    # dcc.Input(value='MTL', type='text'),

    # html.Label('Slider'),
    # dcc.Slider(
    #     min=0,
    #     max=9,
    #     marks={i: 'Label {}'.format(i) if i == 1 else str(i) for i in range(1, 6)},
    #     value=5,
    # ),
    ], 
    # style={'columnCount': 2}
)

@app.callback(
    dash.dependencies.Output('time-graph', 'figure'),
    [dash.dependencies.Input('tags-dropdown', 'value'),
    ])
def update_time_graph(tags_dropdown):
    session = dm.get_session()
    t = session.query(dm.Tag).filter_by(name_en=tags_dropdown).first()
    dfTime = pd.DataFrame([(e.datetime, e.category) for e in t.events])
    dfTime = dfTime.groupby( pd.Grouper(key=0, freq='7d')).count()
    fig = dfTime.iplot(kind='bar', title="Events with tag %s %s" % (t.name_zh,t.name_en), asFigure=True)
    session.close()
    return fig

@app.callback(
    dash.dependencies.Output('lawyer-table', 'data'),
    [dash.dependencies.Input('tags-dropdown', 'value'),
    ])
def update_lawyer_table(tags_dropdown):
    session = dm.get_session()
    lawyers_count = {}

    t = session.query(dm.Tag).filter_by(name_en=tags_dropdown).first()
    for e in t.events:
        for l in e.lawyers.all()+e.lawyers_atk.all()+e.lawyers_def.all():
            try:
                lawyers_count[l]+=1
            except KeyError:
                lawyers_count[l]=1
    dfLawyer = pd.DataFrame([(l.name_zh, l.name_en, c) for l,c in lawyers_count.items()],
                            columns=lawyer_table_cols,
                            )
    # print(dfLawyer)
    data = dfLawyer.sort_values('Events count',ascending=False).to_dict("rows")
    print(data)

    session.close()
    return data

@app.callback(
    dash.dependencies.Output('lawyer-tag-graph', 'figure'),
    [dash.dependencies.Input('lawyer-table', 'active_cell'),
     dash.dependencies.Input('lawyer-table', 'derived_virtual_data'),
    ])
def update_lawyer_tag_graph(active_cell, derived_virtual_data):
    if not active_cell: return None

    session = dm.get_session()
    
    r,c = active_cell
    row = derived_virtual_data[r]
    name_en = row['Name Eng']
    name_zh = row['Name Chi']
    l = session.query(dm.Lawyer).filter_by(name_en=name_en, name_zh=name_zh).first()
    tags_count = {}
    for e in l.events.all()+l.events_atk.all()+l.events_def.all():
        for t in e.tags:
            try:
                tags_count[t]+=1
            except KeyError:
                tags_count[t]=1
    dfTags = pd.DataFrame([(t.name_zh, t.name_en, c) for t,c in tags_count.items()],
                        columns=['zh','en','count'],
                        )
    fig = dfTags.iplot(kind='pie', labels="en", values="count", title="Tags of case by %s %s" %(name_zh,name_en), asFigure=True)
    session.close()
    return fig

if __name__ == '__main__':
    app.run_server(debug=True)
