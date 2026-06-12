import re
import os

def clean_csv_file():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    input_path = os.path.join(base_dir, "data", "ecommercereviews.csv")
    output_path = os.path.join(base_dir, "data", "ecommercereviews_clean.csv")
    
    with open(input_path, "r", encoding="utf-8") as fin:
        lines = fin.readlines()
        
    cleaned_lines = []
    
    # Header cleaning
    header = lines[0].strip().rstrip(';')
    if header.startswith('"') and header.endswith('"'):
        header = header[1:-1]
    # Remove any extra semicolons from column names
    header = re.sub(r';+$', '', header)
    cleaned_lines.append(header + "\n")
    
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
            
        # Strip trailing semicolons first
        stripped = re.sub(r';+$', '', stripped)
        
        # If the entire line is wrapped in double quotes
        if stripped.startswith('"') and stripped.endswith('"'):
            # Unquote it
            stripped = stripped[1:-1]
            # Replace double-double quotes inside with a single double quote
            # But only if it's meant to be a quote character in the text.
            # Usually, standard CSV double-double quotes represent a literal double quote inside a quoted field.
            # Since we unquoted the whole line, we should unescape quotes.
            stripped = stripped.replace('""', '"')
            
        cleaned_lines.append(stripped + "\n")
        
    with open(output_path, "w", encoding="utf-8") as fout:
        fout.writelines(cleaned_lines)
        
    print("CSV cleaned successfully!")

if __name__ == "__main__":
    clean_csv_file()
