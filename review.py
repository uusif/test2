import logging
import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()
from azure.cosmos import CosmosClient
import azure.functions as func
import openai

app = func.FunctionApp()

# database information
ENDPOINT = os.getenv('endUrl')
KEY = os.getenv('cosmodbkey')
client = CosmosClient(url=ENDPOINT, credential=KEY)
database = client.get_database_client(os.getenv('DATABASE_NAME'))
container = database.get_container_client(os.getenv('CONTAINER_NAME'))

#openAI API
api_key = os.getenv('openaiapikey')
openai.api_key = api_key



#create 3 functions
#////////

#function 1: return a json list of all movies in your DB
def getMovies():
    movie_list = []
    for item in container.query_items(query='SELECT  c.title, c.releaseYear, c.genre, c.coverUrl From c', enable_cross_partition_query=True):
        movie_list.append(item)
    return(json.dumps(movie_list, indent=True))

# print(getMovies())

# # #////////

# # #function 2: create a function that returns a list of movies by year. User selects the year. 

def getMoviesByYear(year):
    movie_list = []
    for item in container.query_items(query = f'SELECT c.title, c.releaseYear, c.genre, c.coverUrl From c WHERE c.releaseYear = {year}', enable_cross_partition_query=True):
        movie_list.append(item)
    return json.dumps(movie_list, indent = True)

# year_input = input('Enter the year: ')
# year = "'"+ year_input + "'"
# print(getMoviesByYear(year))

# #/////////

# #function 3: summary generated by AI


#function to generate the summary for the selected movie
def generate_summary(movie_name):
    response = openai.chat.completions.create(
        model = "gpt-3.5-turbo",
        messages=[
            {"role":"user", "content": f"Summarize the movie: {movie_name} in 2 sentences"}
            ],
        temperature=1,
        max_tokens = 200,
    )
    return response.choices[0].message.content

#generate the data. user inputs the movie and the generated summary is included as a part of the data
def getMoviesBySummary(title):
    movie_list = []
    for item in container.query_items(query = f'SELECT c.title, c.releaseYear, c.genre, c.coverUrl From c WHERE LOWER(c.title) = @title', parameters = [dict(name='@title', value = title.lower())], enable_cross_partition_query=True):
        movie_summary = generate_summary(item['title'])
        item['generatedSummary'] = movie_summary
        movie_list.append(item)
    return json.dumps(movie_list, indent = True)

# title_input = input('Enter movie name: ')
# print(getMoviesBySummary(title_input))


#API SET UP
# first API - this just returns all movies in the URL
@app.function_name('getMovies')
@app.route(route="getMovies", auth_level=func.AuthLevel.ANONYMOUS)
def main(req: func.HttpRequest) -> func.HttpResponse:
    movie_list = getMovies()
    if movie_list:
        movie_data = json.loads(movie_list)
        formatted_movie_list = json.dumps(movie_data, indent = 4)
        return func.HttpResponse(
            body = formatted_movie_list,
            mimetype="application/json",
            status_code = 200
        )
    else:
        return func.HttpResponse(
            "No movies found",
            status_code= 404
        )

# second API - this returns movies by year. the user inputs the year into the URL
@app.function_name('getMoviesByYear')
@app.route(route='getMoviesByYear/{year}',auth_level=func.AuthLevel.ANONYMOUS)
def main(req:func.HttpRequest) -> func.HttpResponse:
    year = req.route_params.get('year')
    if year:
        try:
            year_str = "'"+year+"'"
        except ValueError:
            return func.HttpResponse("invalid year parameter. Please provide a valid year parameter", status_code=404)
        movie_list = getMoviesByYear(year_str)
        if len(movie_list) == 2 :
            return func.HttpResponse(
                "No movies found for the specified year",
                 status_code=200)
        else:
            return func.HttpResponse(
                body = movie_list,
                mimetype="application/json",
                status_code=200
            )
            
#third API - select movie and generated movie summary
@app.function_name('getMovieSummary')
@app.route(route='getMovieSummary/{title}',auth_level=func.AuthLevel.ANONYMOUS)
def main(req:func.HttpRequest) -> func.HttpResponse:
    title = req.route_params.get('title')
    movie_list = getMoviesBySummary(title)
    if len(movie_list) == 2 :
        return func.HttpResponse(
            "No movies found under specified title",
            status_code=200
        )
    else:
        return func.HttpResponse(
            body = movie_list,
            mimetype="application/json",
            status_code=200
        )


##test API
@app.route(route="http_trigger", auth_level=func.AuthLevel.ANONYMOUS)
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
