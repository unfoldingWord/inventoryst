## Description
Inventoryst is a script to gather relevant information from all kinds of platforms and store that information into Markdown (`.md`) files.
The intent is to have all relevant information ready in one place. 

## Setup and run
### Manual
1) Clone this repository
```bash
git clone unfoldingword/inventoryst
```

2) Setup and activate Python virtual environment
```bash
cd inventoryst
python -m venv venv
source venv/bin/activate
```

3) Install requirements
```bash
pip install -r requirements.txt
```

4) Configure your `.env` file
Use the file `example.env` for guidance

5) Run the script
```bash
python main.py
```

### Docker
1) Pull the docker file
```bash
docker pull unfoldingword/inventoryst
```

2) Configure the .env file
Use the file `example.env` for guidance

3) Run your container
```bash
docker run --rm --env-file=.env -v /path/to/markdown_files:/app/output unfoldingword/inventoryst
```