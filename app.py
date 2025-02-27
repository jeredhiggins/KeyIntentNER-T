import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html, callback_context
from dash.dash_table import DataTable
from dash.dependencies import Output, Input, State
import plotly.express as px
import spacy
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from gliner_spacy.pipeline import GlinerSpacy
import warnings
import os
import gc
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress specific warnings
warnings.filterwarnings("ignore", message="The sentencepiece tokenizer")

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY, 'https://use.fontawesome.com/releases/v5.8.1/css/all.css'])
server = app.server

# Reference absolute file path 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIES_FILE = os.path.join(BASE_DIR, 'google_categories.txt')

# Configuration for GLiNER integration
custom_spacy_config = {
    "gliner_model": "urchade/gliner_small-v2.1",
    "chunk_size": 128,
    "labels": ["person", "organization", "location", "event", "work_of_art", "product", "service", "date", "number", "price", "address", "phone_number", "misc"],
    "threshold": 0.5
}

# Model variables for lazy loading
nlp = None
sentence_model = None
google_categories = []

# Function to lazy load NLP model
def get_nlp():
    global nlp
    if nlp is None:
        try:
            logger.info("Loading spaCy model")
            nlp = spacy.blank("en")
            nlp.add_pipe("gliner_spacy", config=custom_spacy_config)
            logger.info("spaCy model loaded successfully")
        except Exception as e:
            logger.exception("Error loading spaCy model")
            raise
    return nlp

# Function to lazy load sentence transformer model
def get_sentence_model():
    global sentence_model
    if sentence_model is None:
        sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
    return sentence_model

# Load Google's content categories
def load_google_categories():
    global google_categories
    if not google_categories:
        try:
            with open(CATEGORIES_FILE, 'r') as f:
                google_categories = [line.strip() for line in f]
        except Exception as e:
            google_categories = []
    return google_categories

# Function to perform NER using GLiNER with spaCy
def perform_ner(text):
    try:
        doc = get_nlp()(text)
        return [(ent.text, ent.label_) for ent in doc.ents]
    except Exception as e:
        return []

# Function to extract entities using GLiNER with spaCy
def extract_entities(text):
    try:
        doc = get_nlp()(text)
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        return entities if entities else ["No specific entities found"]
    except Exception as e:
        return ["Error extracting entities"]

# Function to precompute category embeddings
def compute_category_embeddings():
    try:
        categories = load_google_categories()
        return get_sentence_model().encode(categories)
    except Exception as e:
        return []

# Function to perform topic modeling using sentence transformers
def perform_topic_modeling_from_similarities(similarities):
    try:
        categories = load_google_categories()
        top_indices = similarities.argsort()[-3:][::-1]
        
        best_match = categories[top_indices[0]]
        second_best = categories[top_indices[1]]
        
        if similarities[top_indices[0]] > similarities[top_indices[1]] * 1.1:
            return best_match
        else:
            return f"{best_match} , {second_best}"
    except Exception as e:
        return "Error in topic modeling"

# Function to sort keywords by intent feature
def sort_by_keyword_feature(f):
    if type(f) != str:
        return "other"
    f = f.lower()

    informational_keywords = [
        "advice", "help", "how do i", "how does", "how to", "ideas", "information", "tools", "list", 
        "resources", "tips", "tutorial", "diy", "ways to", "what does", "what is", "what was", "where are", "where does", 
        "where can", "where is", "where was", "when is", "when are", "when was", "where to", "who is", "who said", "who wrote", 
        "who are", "why are", "who was", "why is", "examples", "explained", "meaning of", "definition", "benefits of", "uses of", 
        "overview", "summary", "report", "study",  "analysis", "research", "insight", "data", "facts", "details", "background", 
        "context", "news", "history", "documentation", "article", "paper", "blog", "forum", "discussion", "commentary", 
        "opinion", "perspective", "viewpoint", "guide", "difference between", "types of"
    ]

    navigational_keywords = [
        "facebook", "meta", "twitter", "site", "login", "account", "official website", "homepage", "portal", 
        "signin", "register", "signup", "dashboard", "profile", "settings", "control panel", "main page", 
        "user area", "admin", "control", "access", "entry", "webpage", "navigate", "home", "site map", 
        "directory", "find", "search", "lookup", "index", "online", "internet", "web", "browser", "navigate to", 
        "goto", "landing page", "url", "hyperlink", "link", "web address", "navigate", 
        "web navigation", "website address", "app", "download", "status", "join"
    ]

    local_keywords = [
        "closest", "close", "near me", "my area", "residential", "my zip", "my city", "nearby", "in town", 
        "around here", "local", "near", "vicinity", "local area", "nearest", "surrounding", "within miles", 
        "in my neighborhood", "district", "zone", "region", "near my location", "local services", "community", 
        "local shop", "in my vicinity", "local store", "suburb", "urban area", "within walking distance", 
        "around my place", "within my reach", "close by", "local office", "local branch", "near me now", 
        "in my locale", "within the city", "local market", "in my town", "local spot", "local point", 
        "local guide", "near my house", "local venue", "close to me", "within blocks", "local attractions", 
        "local events", "address"
    ]

    commercial_keywords = [
        "best", "affordable", "budget", "cheap", "expensive", "review", "top", "service", "cost", "average cost", 
        "calculator", "provider", "company", "vs", "companies", "professional", "specialist", "compare", 
        "comparison", "rating", "testimonials", "recommendation", "advisor", "consultant", "expert", "ranking", 
        "leader", "top-rated", "best-selling", "trending", "featured", "highlighted", "recommended", "popular", 
        "favorite", "preferred", "choice", "most reviewed", "highest rated", "highly recommended", "award-winning", 
        "five-star", "customer favorite", "top pick", "critically acclaimed", "editor's choice", "people's choice", 
        "top performer", "best value", "best overall", "best quality", "best price", "most trusted", "leading brand", 
        "popular choice", "most popular", "fees", "pros and cons"
    ]

    transactional_keywords = [
        "price", "quotes", "pricing", "purchase", "rates", "how much", "same day", "same-day", "buy", "order", 
        "discount", "deal", "offers", "sale", "checkout", "book", "reservation", "reserve", "bargain", "coupon", 
        "promo", "rebate", "clearance", "markdown", "buy one get one", "bogo", "special", "exclusive", "bundle", 
        "package", "subscription", "membership", "payment", "installment", "financing", "contract", "billing", 
        "invoice", "ticket", "admission", "entry", "enrollment", "register", "sign up", "pre-order", "e-commerce", 
        "shopping cart"
    ]

    if any(keyword in f for keyword in informational_keywords):
        return "informational"
    if any(keyword in f for keyword in navigational_keywords):
        return "navigational"
    if any(keyword in f for keyword in local_keywords):
        return "local"
    if any(keyword in f for keyword in commercial_keywords):
        return "commercial investigation"
    if any(keyword in f for keyword in transactional_keywords):
        return "transactional"

    return "other"

# Optimized batch processing of keywords
def batch_process_keywords(keywords, batch_size=8):
    processed_data = {'Keywords': [], 'Intent': [], 'NER Entities': [], 'Google Content Topics': []}
    
    try:
        sentence_model = get_sentence_model()
        category_embeddings = compute_category_embeddings()
        
        for i in range(0, len(keywords), batch_size):
            logger.info(f"Processing {len(keywords)} keywords")
            batch = keywords[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}")
            batch_embeddings = sentence_model.encode(batch, batch_size=batch_size, show_progress_bar=False)
            
            intents = [sort_by_keyword_feature(kw) for kw in batch]
            entities = [extract_entities(kw) for kw in batch]
            
            similarities = cosine_similarity(batch_embeddings, category_embeddings)
            Google_Content_Topics = [perform_topic_modeling_from_similarities(sim) for sim in similarities]
            
            processed_data['Keywords'].extend(batch)
            processed_data['Intent'].extend(intents)
            
            processed_entities = []
            for entity_list in entities:
                entity_strings = []
                for entity in entity_list:
                    if isinstance(entity, tuple):
                        entity_strings.append(f"{entity[0]} ({entity[1]})")
                    else:
                        entity_strings.append(str(entity))
                processed_entities.append(", ".join(entity_strings))
            
            processed_data['NER Entities'].extend(processed_entities)
            processed_data['Google Content Topics'].extend(Google_Content_Topics)
            
            # Force garbage collection
            gc.collect()
        logger.info("Keyword processing completed successfully")
    except Exception as e:
        logger.exception("An error occurred in batch_process_keywords")
    
    return processed_data

# Main layout of the dashboard
app.layout = dbc.Container([
    dcc.Store(id='models-loaded', data=False),
    dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("About", href="#about", external_link=True)),
        dbc.NavItem(dbc.NavLink("Contact", href="#contact", external_link=True)),
    ],
    brand="KeyIntentNER-T",
    brand_href="https://github.com/jeredhiggins/KeyIntentNER-T",
    color="#151515",
    dark=True,
    brand_style={"background": "linear-gradient(to right, #ff7e5f, #feb47b)", "-webkit-background-clip": "text", "color": "transparent", "textShadow": "0 0 1px #ffffff, 0 0 3px #ff7e5f, 0 0 5px #ff7e5f"},
),

    dbc.Row(dbc.Col(html.H1('Keyword Intent, Named Entity Recognition (NER), & Google Topic Modeling Dashboard', className='text-center text-light mb-4 mt-4'))),

    dbc.Row([
        dbc.Col([
            dbc.Label('Enter keywords (one per line, maximum of 100):', className='text-light'),
            dcc.Textarea(id='keyword-input', value='', style={'width': '100%', 'height': 100}),
            dbc.Button('Submit', id='submit-button', color='primary', className='mb-3', disabled=True),
            dbc.Alert(id='alert', is_open=False, duration=4000, color='danger', className='my-2'),
            dbc.Alert(id='processing-alert', is_open=False, color='info', className='my-2'),
        ], width=6)
    ], justify='center'),
    
    dbc.Row([
        dbc.Col([
            dcc.Loading(
                id="loading",
                type="default",
                children=[html.Div(id="loading-output", className="my-4")]
            ),
        ], width=12)
    ], justify='center', className="mb-4"),

    dbc.Row(dbc.Col(dcc.Graph(id='bar-chart'), width=12)),

    dbc.Row([
        dbc.Col([
            dbc.Label('View all keyword data for each intent category:', className='text-light mt-4'),
            dcc.Dropdown(
                id='table-intent-dropdown',
                options=[],
                placeholder='Select an Intent',
                className='text-dark'
            ),
        ], width=6)
    ], justify='center'),

    dbc.Row(dbc.Col(
        html.Div(id='keywords-table', style={'width': '100%'}),
        width=12
    )),

    dbc.Row(dbc.Col(
        dbc.Button('Download CSV For All Keywords', id='download-button', color='success', className='my-5', disabled=True),
        width=12
    ), justify='center'),

    dcc.Download(id='download'),
    dcc.Store(id='processed-data'),

# Explanation content
    dbc.Row([
        dbc.Col([
            html.Div([
                dbc.Card([
                    dbc.CardBody([
                        html.H3([html.I(className="fas fa-info-circle mr-2"), "About KeyIntentNER-T"], className="card-title text-warning"),
                        html.P("This tool provides valuable keyword insights for SEO and digital marketing professionals. Enter a list of keywords and get insights into Keyword Intent, NLP Entities extracted via NER (Named Entity Recognition), & Topics. I created KeyIntentNER-T as an example of how to use more modern NLP methods to gain insights into shorter text strings (keywords) and how this information may be understood by search engines using similar techniques.", className="card-text"), 
                    ])
                ], className="mb-4 shadow-sm"),
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H3([html.I(className="fas fa-pen mr-2"), "Notes on the data"], className="card-title text-success"),
                                dbc.ListGroup([
                                    dbc.ListGroupItem([html.I(className="fas fa-check mr-2"), "Keyword Intent is determined using a custom function that looks for the presence of specific terms and then classifies it into one of six predefined intent categories: 'informational', 'navigational', 'local', 'commercial investigation', 'transactional', or 'other'."]),
                                    dbc.ListGroupItem([html.I(className="fas fa-check mr-2"), "NLP Entities are determined using GLiNER, an advanced Named Entity Recognition (NER) model that is better at classifying shorter text strings. Additionally, Entitites are mapped to all Entity Types included in the Google Cloud Natural Language API."]),
                                    dbc.ListGroupItem([html.I(className="fas fa-check mr-2"), "Topics are determined by matching keywords to topics from Google's well-known Content and Product taxonomies."]),
                                    dbc.ListGroupItem([html.I(className="fas fa-check mr-2"), "Since this tool is doing a lot behind the scenes, keyword processing can take anywhere from 30 seconds up to ~2 minutes."]),
                                ], flush=True)
                            ])
                        ], className="mb-4 shadow-sm")
                    ], md=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H3([html.I(className="fas fa-chart-line mr-2"), "Benefits for SEO"], className="card-title text-info"),
                                dbc.ListGroup([
                                    dbc.ListGroupItem([html.I(className="fas fa-arrow-up mr-2"), "Improved content strategy by focusing your SEO efforts on creating more relevant/helpful content that addresses the search intent for keywords."]),
                                    dbc.ListGroupItem([html.I(className="fas fa-bullseye mr-2"), "Enhanced keyword targeting by matching keywords to Google's well-known categories, ensuring your content is aligned with popular search themes."]),
                                    dbc.ListGroupItem([html.I(className="fas fa-users mr-2"), "Better understanding of what kind of information a person is looking for."]),
                                    dbc.ListGroupItem([html.I(className="fas fa-robot mr-2"), "Better understanding of how keywords can be interpreted by search engines."]),
                                ], flush=True)
                            ])
                        ], className="mb-4 shadow-sm")
                    ], md=6),
                ]),
                dbc.Card([
                    dbc.CardBody([
                        html.H3([html.I(className="fas fa-quote-left mr-2"), "GLiNER Model Citation"], className="card-title text-light"),
                        html.P([
                            "GLiNER: Generalist Model for Named Entity Recognition using Bidirectional Transformer. ",
                            html.Br(),
                            "Authors: Urchade Zaratiana, Nadi Tomeh, Pierre Holat, Thierry Charnois.",
                            html.Br(),
                            "Year: 2023.",
                            html.Br(),
                            html.A([html.I(className="fas fa-external-link-alt mr-2"), "arXiv:2311.08526"], href="https://arxiv.org/abs/2311.08526", target="_blank", className="btn btn-outline-warning btn-sm mt-2")
                        ], className="card-text"),
                    ])
                ], className="mb-4 shadow-sm")
            ], id="about")
        ], width=12)
    ], className="mt-5"),

    # Contact section
    dbc.Row([
        dbc.Col([
            html.Div([
                dbc.Card([
                    dbc.CardBody([
                        html.H3([html.I(className="fas fa-envelope mr-2"), "Contact"], className="card-title text-info"),
                        html.P([
                            "For questions or if you are interested in building custom SEO dash apps, contact me at: ",
                            html.A("jrad.seo@gmail.com", href="mailto:jrad.seo@gmail.com", className="text-info")
                        ], className="card-text"),
                    ])
                ], className="mb-4 shadow-sm")
            ], id="contact")
        ], width=12)
    ], className="mt-4 mb-4"),

# JS for smooth scrolling
    html.Div([
        html.Script('''
            document.addEventListener("DOMContentLoaded", function() {
                var links = document.querySelectorAll("a[href^='#']");
                links.forEach(function(link) {
                    link.addEventListener("click", function(e) {
                        e.preventDefault();
                        var targetId = this.getAttribute("href").substring(1);
                        var targetElement = document.getElementById(targetId);
                        if (targetElement) {
                            targetElement.scrollIntoView({
                                behavior: "smooth",
                                block: "start"
                            });
                        }
                    });
                });
            });
        ''')
    ]),

], fluid=True)

@app.callback(
    [Output('models-loaded', 'data'),
     Output('submit-button', 'disabled'),
     Output('alert', 'is_open'),
     Output('alert', 'children'),
     Output('alert', 'color'),
     Output('processed-data', 'data'),
     Output('loading-output', 'children'),
     Output('processing-alert', 'is_open'),
     Output('processing-alert', 'children')],
    [Input('models-loaded', 'data'),
     Input('submit-button', 'n_clicks')],
    [State('keyword-input', 'value')]
)
def combined_callback(loaded, n_clicks, keyword_input):
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    try:
        if triggered_id == 'models-loaded':
            return handle_model_loading(loaded)
        elif triggered_id == 'submit-button':
            return handle_keyword_processing(n_clicks, keyword_input)
        else:
            return loaded, False, False, "", "success", None, '', False, ''
    except Exception as e:
        logger.exception("An error occurred in combined_callback")
        return loaded, False, True, f"An error occurred: {str(e)}", "danger", None, '', False, ''

def handle_model_loading(loaded):
    if not loaded:
        try:
            # Lazy loading will occur when models are first used
            return True, False, True, "Models ready to load", "success", None, '', False, ''
        except Exception as e:
            return False, True, True, f"Error preparing models: {str(e)}", "danger", None, '', False, ''
    return loaded, not loaded, False, "", "success", None, '', False, ''

def handle_keyword_processing(n_clicks, keyword_input):
    if n_clicks is None or not keyword_input:
        return True, False, False, "", "success", None, '', False, ''

    keywords = [kw.strip() for kw in keyword_input.split('\n')[:100] if kw.strip()]
    processed_data = batch_process_keywords(keywords)

    return True, False, False, "", "success", processed_data, '', True, "Keyword processing complete!"

# Callback for updating the bar chart
@app.callback(
    Output('bar-chart', 'figure'),
    [Input('processed-data', 'data')]
)
def update_bar_chart(processed_data):
    logger.info("Updating bar chart")
    if processed_data is None:
        logger.info("No processed data available")
        return {
            'data': [],
            'layout': {
                'height': 0,
                'annotations': [{
                    'text': '',
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 28}
                }]
            }
        }

    df = pd.DataFrame(processed_data)
    logger.info(f"Data shape: {df.shape}")
    intent_counts = df['Intent'].value_counts().reset_index()
    intent_counts.columns = ['Intent', 'Count']

    fig = px.bar(intent_counts, x='Intent', y='Count', color='Intent', 
                 title='Keyword Intent Distribution', 
                 color_discrete_sequence=px.colors.qualitative.Dark2)
    
    fig.update_layout(
        plot_bgcolor='#222222',
        paper_bgcolor='#222222',
        font_color='white',
        height=400,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig

# Callback for updating the dropdown and download button
@app.callback(
    [Output('table-intent-dropdown', 'options'),
     Output('download-button', 'disabled')],
    [Input('processed-data', 'data')]
)
def update_dropdown_and_button(processed_data):
    if processed_data is None:
        return [], True

    df = pd.DataFrame(processed_data)
    intents = df['Intent'].unique()
    options = [{'label': intent, 'value': intent} for intent in intents]
    return options, False

# Callback for updating the keywords table
@app.callback(
    Output('keywords-table', 'children'),
    [Input('table-intent-dropdown', 'value')],
    [State('processed-data', 'data')]
)
def update_keywords_table(selected_intent, processed_data):
    if processed_data is None or selected_intent is None:
        return html.Div()

    df = pd.DataFrame(processed_data)
    filtered_df = df[df['Intent'] == selected_intent]

    table = DataTable(
        columns=[{"name": i, "id": i} for i in filtered_df.columns],
        data=filtered_df.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'whiteSpace': 'normal', 'height': 'auto', 'minWidth': '100px', 'width': '100px', 'maxWidth': '100px'},
        style_header={'backgroundColor': 'rgb(30, 30, 30)', 'color': 'white'},
        style_data={'backgroundColor': 'rgb(50, 50, 50)', 'color': 'white'},
        sort_action='native',
        page_action='native',
        page_current=0
    )
    return table

# Callback for downloading CSV
@app.callback(
    Output('download', 'data'),
    [Input('download-button', 'n_clicks')],
    [State('processed-data', 'data')]
)
def download_csv(n_clicks, processed_data):
    if n_clicks is None or processed_data is None:
        return None

    df = pd.DataFrame(processed_data)
    csv_string = df.to_csv(index=False, encoding='utf-8')
    return dict(content=csv_string, filename="KeyIntentNER-T_keyword_analysis.csv")

# Modified the server run command for HuggingFace Spaces
if __name__ == "__main__":
    app.run_server(debug=False, host="0.0.0.0", port=7860)
