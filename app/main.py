from fastapi import FastAPI
app = FastAPI()

@app.get("/items/{item_id}")
def get_item(item_id: str):
    return {"item_id": item_id}


@app.post("/items/")
def create_item():
    return {"message": "Item created"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}

AWS_KEYS = JSFHJKSDFJSDBFJDFHSHGFJGFJGDJKL