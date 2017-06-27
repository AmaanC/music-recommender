import pandas as pd
from scipy.spatial.distance import cosine
from sqlalchemy import create_engine, Table, MetaData
from flask import Flask, jsonify, make_response, request


# Setup
app = Flask(__name__, static_url_path='') # For the API
engine = create_engine('postgresql:///testdb') # Connect to the DB
source_table_name = 'source_data' # This contains the raw data we got from the CSV file. It's used to compute the next 2 tables
band_sim_table_name = 'band_sim_matrix' # We compute the recommended bands and store it in this table
band_table_name = 'band_recs' # We compute the recommended bands and store it in this table

N_SIMILAR_BANDS = 10 # Find 10 similar bands for each band

def init():
    '''
        Read the SQL tables to memory (in DataFrames) and make them available globally.
    '''
    global insert_user_stmt, source_table, source_df, band_rec_df, band_similarity_matrix
    meta = MetaData()
    try:
        source_df = pd.read_sql_table(source_table_name, engine, index_col='index')
    except ValueError as e:
        print('Source table missing. Loading from CSV, and writing to DB.')
        source_df = pd.read_csv('data.csv')
        source_df.columns = [c.lower() for c in source_df.columns]
        source_df.to_sql(source_table_name, engine)
        print('Wrote source data to DB.')
    source_table = Table(source_table_name, meta, autoload=True, autoload_with=engine)
    insert_user_stmt = source_table.insert().values()
    try:
        band_similarity_matrix = pd.read_sql_table(band_sim_table_name, engine, index_col='index')
        band_rec_df = pd.read_sql_table(band_table_name, engine, index_col='index')
    except ValueError as e:
        print(e)
        calc_recs()

def write_df_to_db():
    print('Writing to db')
    band_similarity_matrix.to_sql(band_sim_table_name, engine, if_exists='replace')
    band_rec_df.to_sql(band_table_name, engine, if_exists='replace')
    return 'Wrote dataframe to db'

def getScore(history, similarities):
   return sum(history * similarities) / sum(similarities)

@app.route('/api/v1.0/recalc')
def calc_recs():
    '''
        Calculate the recommendation tables using the source data.
        1) The source table is used to calculate a similarity matrix of each band in relation to another. This allows us to
        recommend "similar bands". For example, given Metallica, we can recommend Iron Maiden.
        2) The source table and the band recommendation table are used to find the bands this particular user is most likely to
        enjoy. For example, if you like a lot of rock bands, it'll recommend a list of bands most similar to those.
    '''
    global source_df, band_rec_df, band_similarity_matrix
    # Step 1) Item based collaborative filtering
    print('Calculating band similarities')

    data_bands = source_df.drop('user', 1)
    band_similarity_matrix = pd.DataFrame(index=data_bands.columns, columns=data_bands.columns)


    for i in range(0, len(band_similarity_matrix.columns)):
        # Loop through the columns for each column
        for j in range(0, len(band_similarity_matrix.columns)):
          # Fill in placeholder with cosine similarities
          band_similarity_matrix.ix[i, j] = 1 - cosine(data_bands.ix[:,i], data_bands.ix[:,j])
    
    band_rec_df = pd.DataFrame(index=band_similarity_matrix.columns, columns=range(1, N_SIMILAR_BANDS + 1))
    for i in range(0, len(band_similarity_matrix.columns)):
       band_rec_df.ix[i, :N_SIMILAR_BANDS] = band_similarity_matrix.ix[0:, i].sort_values(ascending=False)[:N_SIMILAR_BANDS].index

    # Done! Now we have recommendations for every band
    return write_df_to_db()

def get_rec_for_user(idx):
    '''
        Calculates the best bands to recommend to a user and returns a Pandas Series with the co-effecients for each
        band.
        The process:
        We look at all the bands, and for every band that the user hasn't heard, we get the top N similar bands.
        For these N bands, we calculate a score based on the user's history.
        For example:
        The user hasn't heard Coldplay.
        Coldplay's most similar bands are:
            1                  coldplay
            2     red hot chili peppers
            3               snow patrol
            4              jack johnson
            5                bloc party
            6                     keane
            7                      muse
            8                 the kooks
            9               the killers
            10                radiohead
        Coldplay's score for this user is directly proportional to X, where X is the number of bands
        in the list above which the user already likes.
    '''
    print('Calculating user similarities')

    data_sims = pd.Series(index=source_df.columns)
    data_bands = source_df.drop('user', 1)

    i = idx
    for j in range(1, len(data_sims.index)):
        product = data_sims.index[j]

        if source_df.ix[i][j] == 1:
            # User's already heard the band, so we don't want to recommend it again
            data_sims.ix[j] = 0
        else:
            # We'll find bands that are similar to this unheard band
            product_top_names = band_rec_df.ix[product][1:N_SIMILAR_BANDS]
            # Then let's put these bands in descending order of how similar they are
            product_top_sims = band_similarity_matrix.ix[product].sort_values(ascending=False)[1:N_SIMILAR_BANDS]
            # We'll get the bands that user has heard out of the similar ones
            user_purchases = data_bands.ix[idx, product_top_names]

            # The score basically determines the ratio like this:
            # There are 10 bands similar to X, the current "product"
            # Out of these 10 bands, the user likes 6
            # Using these and the similarity factor of the bands a score is calculated in getScore
            data_sims.ix[j] = getScore(user_purchases, product_top_sims)

    return data_sims.sort_values(ascending=False)

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.errorhandler(404)
def not_found(error):
    print(request.path)
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.route('/api/v1.0/band/')
def list_bands():
    return jsonify({
        'bands': list(source_df.columns[1:]) # Skipping the user column
    })

@app.route('/api/v1.0/band/<path:name>')
def rec_band(name):
    '''
        JSON formatted response listing similar bands
    '''
    print(name in band_rec_df.index)
    if name in band_rec_df.index:
        # return jsonify(a=list(band_rec_df[band_rec_df['index'] == 'abba']))
        similar = list(
            band_rec_df.loc[name].ix[1:]
        )
    else:
        return make_response(
            jsonify({
                'error': 'Band {} not found'.format(name)
            }),
            404
        )

    resp_dict = {
        'name': name,
        'similar': similar
    }
    return jsonify(resp_dict)

@app.route('/api/v1.0/user/<int:id>')
def rec_user(id):
    '''
        Show the bands that a user already likes, and the bands we'd recommend to the user.
    '''
    try:
        limit = int(request.args.get('limit'))
    except:
        limit = 10
    if id not in source_df.index:
        return make_response(
            jsonify({
                'error': 'User {} not found'.format(id)
            }),
            404
        )
    recs = list(get_rec_for_user(id).head(limit).index)
    like_list = list(source_df.iloc[id, :].loc[source_df.iloc[id, :] == 1].index)
    resp_dict = {
        'user': id,
        'likes': like_list,
        'recommendations': recs
    }
    return jsonify(resp_dict)

@app.route('/api/v1.0/user/', methods=['GET'])
def list_users():
    return jsonify({
        'num_of_users': source_df.shape[0]
    })

@app.route('/api/v1.0/user/', methods=['POST'])
def add_user():
    global source_df
    data = request.get_json(force=True)
    if not data or not data['likes']:
        return jsonify({
            'error': 'Need a JSON request formatted like: { "likes": ["simple plan", "abba", "coldplay"] }'
        })
    elif all(band_name in source_df.columns for band_name in data['likes']):
        print(data)
        user_data = dict.fromkeys(source_df.columns, 0)
        for band_name in data['likes']:
            if band_name != 'index' and band_name != 'user':
                user_data[band_name] = 1
        # Add to pandas DF here
        source_df = source_df.append(user_data, ignore_index=True)
        user_data['index'] = source_df.shape[0] - 1 # Subtract 1 since we *just* added an index
        # Add to db here
        
        conn = engine.connect()
        conn.execute(insert_user_stmt, **user_data)
        conn.close()

        return jsonify({
            'user_id': user_data['index']
        })
    else:
        return jsonify({
            'error': 'One or more bands were not found in the list.'
        })

if __name__ == '__main__':
    init()
    app.run(debug=True)
