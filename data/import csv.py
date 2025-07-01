import csv

input_file = 'data/Artist.csv'
output_file = 'twitter_ids.md'

with open(input_file, newline='', encoding='utf-8') as csvfile, open(output_file, 'w', encoding='utf-8') as mdfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        twitter_id = row.get('twitter_id', '').strip()
        if twitter_id:
            mdfile.write(f"{twitter_id}\n")