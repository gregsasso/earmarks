import pandas as pd
import numpy as np
import yaml

#load data

df_earmarks = pd.read_csv(r"C:/Users/gregs/Dropbox/Python Projects/Earmarks/FY2022-Congressionally-Directed-Spending-BPC.csv") #earmark data from bipartisan policy center: https://bipartisanpolicy.org/blog/congressionally-directed-spending-fy2022-dataset/
house_les = pd.read_excel(r"https://thelawmakers.org/wp-content/uploads/2023/04/CELHouse117LES2.xls") #house legislative effectiveness scores from center for effective lawmaking
senate_les=pd.read_excel(r"https://thelawmakers.org/wp-content/uploads/2023/04/CELSenate117LES2.xls") #senate legislative effectiveness scores from center for effective lawmaking


#Committee membership for members of 117th congress from https://github.com/unitedstates/congress-legislators
with open(r'C:/Users/gregs/Dropbox/Python Projects/Earmarks/committee_memberships.yml', 'r') as f:
    data = yaml.safe_load(f)
    
# Create a list of dataframes, one for each committee
dfs = []
for committee_name, committee_members in data.items():
    members = []
    for member in committee_members:
        member_dict = {
            'committee': committee_name,
            'member_name': member['name'],
            'party_status': member['party'],
            'rank': member['rank'],
            'bioguide': member['bioguide']
        }
        if 'title' in member:
            member_dict['title'] = member['title']
        members.append(member_dict)
    df = pd.DataFrame(members)
    dfs.append(df)

# Concatenate all then drop rank and title
all_members = pd.concat(dfs)
all_members = all_members.drop(['rank', 'title'], axis=1)

#Committee names and thomas_id numbers https://github.com/unitedstates/congress-legislators
with open(r'C:/Users/gregs/Dropbox/Python Projects/Earmarks/committees_historical.yml', 'r') as f:
    data_committee_name = yaml.safe_load(f)
    
# Extract name and thomas_id from each entry
name_list = []
thomas_id_list = []
for entry in data_committee_name:
    name_list.append(entry['name'])
    thomas_id_list.append(entry['thomas_id'])

# Create DataFrame
committee_names = pd.DataFrame({'name': name_list, 'thomas_id': thomas_id_list})

#subset earmark data for relevant categories

df2_earmarks = df_earmarks[['category',
 'agency',
 'account',
 'project',
 'recipient',
 'location',
 'state',
 'amount',
 'origination',
 'requestor_one_full_name',
 'requestor_one_bioguide_id',
 'requestor_one_chamber',
 'requestor_one_party',
 'requestor_two_full_name',
 'requestor_two_bioguide_id',
 'requestor_two_chamber',
 'requestor_two_party']]

#change amount from string to float

df2_earmarks.loc[:,'amount'] = df2_earmarks.loc[:,'amount'].replace('—', 0)
df2_earmarks.loc[:,'amount'] = df2_earmarks.loc[:,'amount'].replace('2,959,000', 2959000)
df2_earmarks.loc[:,'amount'] = df2_earmarks.loc[:,'amount'].astype(float)

#Subset les data and merge into single dataframe
house_les=house_les[['Two-letter state code', 'Indicator for member in bioguide', 'LES 2.0']]
house_les=house_les.rename(columns={'Two-letter state code': 'member_state' , 'Indicator for member in bioguide': 'bioguide', 'LES 2.0': 'LES'})
senate_les=senate_les[['two letter state abbreviation', 'Indicator for member in bioguide', 'LES 2.0']]
senate_les=senate_les.rename(columns={'two letter state abbreviation': 'member_state', 'Indicator for member in bioguide': 'bioguide', 'LES 2.0': 'LES'})
les=pd.concat([house_les, senate_les])

#join earmark and les data, drop redundant columns, and make sure missing data is filled
df_les= pd.merge(df2_earmarks, les, left_on='requestor_one_bioguide_id', right_on='bioguide', how='left')
df_les=df_les.drop(['recipient', 'location', 'bioguide'], axis=1)
df_les[['account', 'requestor_two_full_name', 'requestor_two_bioguide_id', 'requestor_two_chamber', 'requestor_two_party']]=df_les[['account', 'requestor_two_full_name', 'requestor_two_bioguide_id', 'requestor_two_chamber', 'requestor_two_party']].fillna('None')

# Pivot members committee to create columns for each committee and rows for each member
pivoted_members = all_members.pivot(
    index=['member_name', 'party_status', 'bioguide'],
    columns='committee',
    values='committee'
)

# Fill NaN values with 0
pivoted_members = pivoted_members.fillna(0)

# Replace non-zero values with 1
pivoted_members = pivoted_members.replace({committee: 1 for committee in all_members['committee'].unique()})

# Reset the index to turn 'name' back into a column
pivoted_members.reset_index(inplace=True)

#join earmark data and committee data, then drop redundant columns
merged_committees  = pd.merge(df_les, pivoted_members, left_on='requestor_one_bioguide_id', right_on='bioguide', how='left')
merged_committees = merged_committees. drop(['member_name', 'bioguide'], axis=1)

#Add party status and fill missing data for members without committee data
merged_committees.loc[merged_committees['requestor_one_full_name'] == 'Filemon Vela', ['party_status']] = ['majority']
merged_committees.loc[merged_committees['requestor_one_full_name'] == 'Nancy Pelosi', ['party_status']] = ['majority']
merged_committees.loc[merged_committees['requestor_one_full_name'] == 'Steny H. Hoyer', ['party_status']]= ['majority']
merged_committees.loc[merged_committees['requestor_one_full_name'] == 'Tom Reed', ['party_status']] = ['minority']
merged_committees=merged_committees.fillna(0)

#rename committee abbreviations to full names
# Create dictionary to map thomas_id to name
name_dict = dict(zip(committee_names['thomas_id'], committee_names['name']))

# Rename columns based on thomas_id to name mapping
earmarks_committees = merged_committees.rename(columns=name_dict)

#drop irrelvant committees and subcommittees
earmarks_cleaned = earmarks_committees.drop(['Commission on Security and Cooperation in Europe (Helsinki Commission)','House Select Committee on Economic Disparity and Fairness in Growth',
 'House Select Committee on the Climate Crisis',
 'House Select Committee on the Modernization of Congress',
 'House Select Committee to Investigate the January 6th Attack on the United States Capitol'], axis=1)
earmarks_cleaned = earmarks_cleaned.filter(regex='^(?!HS|SS|JS|HL)')

#add committee groupings that match earmark categories
earmarks_cleaned = earmarks_cleaned.reindex(columns = earmarks_cleaned.columns.tolist()
                                  + ['Agriculture, Rural Development, Food and Drug Administration, and Related Agencies',
 'Commerce, Justice, Science, and Related Agencies', 'Defense',
 'Energy and Water Development, and Related Agencies',
 'Financial Services and General Government', 'Homeland Security',
 'Interior, Environment, and Related Agencies',
 'Labor, Health and Human Services, Education, and Related Agencies',
 'Military Construction, Veterans Affairs, and Related Agencies',
 'Transportation, and Housing and Urban Development, and Related Agencies'])

#make sure all entires are int
earmarks_cleaned[['House Committee on Agriculture',
 'House Committee on Appropriations',
 'House Committee on Armed Services',
 'House Committee on Banking and Currency',
 'House Committee on Budget',
 'House Committee on Education and Labor',
 'House Committee on Foreign Affairs',
 'House Committee on Government Operations',
 'House Committee on Homeland Security (Select)',
 'House Committee on House Administration',
 'House Committee on Intelligence (Permanent Select)',
 'House Committee on Interior and Insular Affairs',
 'House Committee on Interstate and Foreign Commerce',
 'House Committee on Judiciary',
 'House Committee on Public Works',
 'House Committee on Rules',
 'House Committee on Science and Astronautics',
 'House Committee on Small Business',
 'House Committee on Standards of Official Conduct',
 "House Committee on Veterans' Affairs",
 'House Committee on Ways and Means',
 'Senate Committee on Aging (Special)',
 'Senate Committee on Agriculture and Forestry',
 'Senate Committee on Appropriations',
 'Senate Committee on Armed Services',
 'Senate Committee on Banking, Housing, and Urban Affairs',
 'Senate Committee on Budget',
 'Senate Committee on Caucus on International Narcotics Control',
 'Senate Committee on Commerce',
 'Senate Committee on Finance',
 'Senate Committee on Foreign Relations',
 'Senate Committee on Government Operations',
 'Senate Committee on Indian Affairs (Select)',
 'Senate Committee on Intelligence (Select)',
 'Senate Committee on Interior and Insular Affairs',
 'Senate Committee on Judiciary',
 'Senate Committee on Labor and Public Welfare',
 'Senate Committee on Public Works',
 'Senate Committee on Rules and Administration',
 'Senate Committee on Small Business (Select)',
 'Senate Committee on Standards and Conduct (Select)',
 "Senate Committee on Veterans' Affairs"]] = earmarks_cleaned[['House Committee on Agriculture',
 'House Committee on Appropriations',
 'House Committee on Armed Services',
 'House Committee on Banking and Currency',
 'House Committee on Budget',
 'House Committee on Education and Labor',
 'House Committee on Foreign Affairs',
 'House Committee on Government Operations',
 'House Committee on Homeland Security (Select)',
 'House Committee on House Administration',
 'House Committee on Intelligence (Permanent Select)',
 'House Committee on Interior and Insular Affairs',
 'House Committee on Interstate and Foreign Commerce',
 'House Committee on Judiciary',
 'House Committee on Public Works',
 'House Committee on Rules',
 'House Committee on Science and Astronautics',
 'House Committee on Small Business',
 'House Committee on Standards of Official Conduct',
 "House Committee on Veterans' Affairs",
 'House Committee on Ways and Means',
 'Senate Committee on Aging (Special)',
 'Senate Committee on Agriculture and Forestry',
 'Senate Committee on Appropriations',
 'Senate Committee on Armed Services',
 'Senate Committee on Banking, Housing, and Urban Affairs',
 'Senate Committee on Budget',
 'Senate Committee on Caucus on International Narcotics Control',
 'Senate Committee on Commerce',
 'Senate Committee on Finance',
 'Senate Committee on Foreign Relations',
 'Senate Committee on Government Operations',
 'Senate Committee on Indian Affairs (Select)',
 'Senate Committee on Intelligence (Select)',
 'Senate Committee on Interior and Insular Affairs',
 'Senate Committee on Judiciary',
 'Senate Committee on Labor and Public Welfare',
 'Senate Committee on Public Works',
 'Senate Committee on Rules and Administration',
 'Senate Committee on Small Business (Select)',
 'Senate Committee on Standards and Conduct (Select)',
 "Senate Committee on Veterans' Affairs"]].astype(int)

#add values to group committee membership by earmark catergory
earmarks_cleaned['Agriculture, Rural Development, Food and Drug Administration, and Related Agencies'] = (earmarks_cleaned['House Committee on Agriculture'] | earmarks_cleaned['House Committee on Public Works'] | earmarks_cleaned['Senate Committee on Agriculture and Forestry']| earmarks_cleaned['Senate Committee on Public Works']).astype(int).fillna(0)
earmarks_cleaned['Commerce, Justice, Science, and Related Agencies'] = (earmarks_cleaned['House Committee on Judiciary'] | earmarks_cleaned['House Committee on Interstate and Foreign Commerce'] | earmarks_cleaned['House Committee on Science and Astronautics'] | earmarks_cleaned['Senate Committee on Commerce']| earmarks_cleaned['Senate Committee on Judiciary'] ).astype(int).fillna(0)
earmarks_cleaned['Defense'] = (earmarks_cleaned['House Committee on Armed Services'] | earmarks_cleaned['House Committee on Intelligence (Permanent Select)'] | earmarks_cleaned['Senate Committee on Armed Services']| earmarks_cleaned['Senate Committee on Intelligence (Select)']).astype(int).fillna(0)
earmarks_cleaned['Energy and Water Development, and Related Agencies'] = (earmarks_cleaned['Senate Committee on Public Works'] | earmarks_cleaned['House Committee on Public Works'] | earmarks_cleaned['House Committee on Science and Astronautics']).astype(int).fillna(0)
earmarks_cleaned['Financial Services and General Government'] = (earmarks_cleaned['House Committee on Appropriations'] | earmarks_cleaned['House Committee on Banking and Currency'] | earmarks_cleaned['House Committee on Budget'] | earmarks_cleaned['House Committee on Government Operations'] | earmarks_cleaned['Senate Committee on Banking, Housing, and Urban Affairs'] | earmarks_cleaned['House Committee on Ways and Means'] | earmarks_cleaned['Senate Committee on Appropriations'] | earmarks_cleaned['Senate Committee on Budget'] | earmarks_cleaned['Senate Committee on Finance']| earmarks_cleaned['Senate Committee on Government Operations'] ).astype(int).fillna(0)
earmarks_cleaned['Homeland Security'] = (earmarks_cleaned['House Committee on Foreign Affairs'] | earmarks_cleaned['House Committee on Homeland Security (Select)'] | earmarks_cleaned['House Committee on Intelligence (Permanent Select)']).astype(int).fillna(0)
earmarks_cleaned['Interior, Environment, and Related Agencies'] = (earmarks_cleaned['House Committee on Interior and Insular Affairs'] | earmarks_cleaned['Senate Committee on Interior and Insular Affairs']).astype(int).fillna(0)
earmarks_cleaned['Labor, Health and Human Services, Education, and Related Agencies'] = (earmarks_cleaned['House Committee on Education and Labor'] | earmarks_cleaned['House Committee on Small Business'] | earmarks_cleaned['Senate Committee on Labor and Public Welfare']).astype(int).fillna(0)
earmarks_cleaned['Military Construction, Veterans Affairs, and Related Agencies'] = (earmarks_cleaned['House Committee on Armed Services'] | earmarks_cleaned ["House Committee on Veterans' Affairs"] | earmarks_cleaned["Senate Committee on Veterans' Affairs"]|earmarks_cleaned['Senate Committee on Armed Services']).astype(int).fillna(0)
earmarks_cleaned['Transportation, and Housing and Urban Development, and Related Agencies'] = (earmarks_cleaned['House Committee on Public Works'] | earmarks_cleaned['Senate Committee on Banking, Housing, and Urban Affairs'] | earmarks_cleaned['Senate Committee on Public Works']).astype(int).fillna(0)

#drop individual committee columns
earmarks_cleaned=earmarks_cleaned.drop(['House Committee on Agriculture',
 'House Committee on Appropriations',
 'House Committee on Armed Services',
 'House Committee on Banking and Currency',
 'House Committee on Budget',
 'House Committee on Education and Labor',
 'House Committee on Foreign Affairs',
 'House Committee on Government Operations',
 'House Committee on Homeland Security (Select)',
 'House Committee on House Administration',
 'House Committee on Intelligence (Permanent Select)',
 'House Committee on Interior and Insular Affairs',
 'House Committee on Interstate and Foreign Commerce',
 'House Committee on Judiciary',
 'House Committee on Public Works',
 'House Committee on Rules',
 'House Committee on Science and Astronautics',
 'House Committee on Small Business',
 'House Committee on Standards of Official Conduct',
 "House Committee on Veterans' Affairs",
 'House Committee on Ways and Means',
 'Senate Committee on Aging (Special)',
 'Senate Committee on Agriculture and Forestry',
 'Senate Committee on Appropriations',
 'Senate Committee on Armed Services',
 'Senate Committee on Banking, Housing, and Urban Affairs',
 'Senate Committee on Budget',
 'Senate Committee on Caucus on International Narcotics Control',
 'Senate Committee on Commerce',
 'Senate Committee on Finance',
 'Senate Committee on Foreign Relations',
 'Senate Committee on Government Operations',
 'Senate Committee on Indian Affairs (Select)',
 'Senate Committee on Intelligence (Select)',
 'Senate Committee on Interior and Insular Affairs',
 'Senate Committee on Judiciary',
 'Senate Committee on Labor and Public Welfare',
 'Senate Committee on Public Works',
 'Senate Committee on Rules and Administration',
 'Senate Committee on Small Business (Select)',
 'Senate Committee on Standards and Conduct (Select)',
 "Senate Committee on Veterans' Affairs"], axis=1)

#create summary column indicating if member served on a committee relevant to the earmark requested
earmarks_cleaned['Relevant_Committee'] = None

# define a function to set the relevant column to 1 if the corresponding value column is 1
def set_relevant(row):
    cat = row['category']
    val_col = cat  # get the name of the corresponding value column
    if row[val_col] == 1:
        row['Relevant_Committee'] = 1
    else:
        row['Relevant_Committee'] = 0
    return row

# apply the function to each row of the dataframe
earmarks_cleaned = earmarks_cleaned.apply(set_relevant, axis=1)

#create dummy variable for being in majority party and only keep party_status_majority
earmarks_cleaned = pd.get_dummies(earmarks_cleaned, columns = ['party_status'])
earmarks_cleaned = earmarks_cleaned.drop(['party_status_minority'], axis=1)

#export cleaned dataframe to csv
earmarks_cleaned.to_csv('earmarks_cleaned2.csv', encoding='utf-8', index=False)