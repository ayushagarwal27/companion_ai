from fastapi import FastAPI

app = FastAPI(title="Companion AI")

@app.get('/')
def root():
    return "Companion AI"