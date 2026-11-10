from fastapi import Depends, FastAPI, HTTPException, status
from typing import List

from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from .models import CategoryDB, ProductDB
from .schemas import CategoryCreate, CategoryResponse, CategoryUpdate, Product, ProductCreate, ProductResponse

from .database import Base, get_db, engine
from .jwt.auth import router as auth_router, get_current_user
from .streaming import router as streaming_router, broker, product_to_dict


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth_router)
app.include_router(streaming_router)

@app.post("/products",response_model=ProductResponse,status_code=status.HTTP_201_CREATED,)
async def create_product(
    product: Product,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_user),
):
    existing_product = (
        db.query(ProductDB)
        .filter(ProductDB.id == product.id)
        .first()
    )

    if existing_product is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with id {product.id} already exists",
        )

    db_product = ProductDB(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
    )

    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    broker.publish("product_created", {"user": username, "product": product_to_dict(db_product)})
    return db_product

@app.get("/products", response_model=List[ProductResponse])
async def get_products(db: Session = Depends(get_db)):
    products = db.query(ProductDB).all()
    return products

@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.delete("/products/{product_id}", response_model=ProductResponse)
async def delete_product(product_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    deleted = product_to_dict(product)
    db.delete(product)
    db.commit()
    broker.publish("product_deleted", {"user": username, "product": deleted})
    return deleted

@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product: ProductCreate, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    db_product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in product.model_dump(exclude={"id"}).items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    broker.publish("product_updated", {"user": username, "product": product_to_dict(db_product)})
    return db_product

# category

@app.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    db_category = CategoryDB(name=category.name)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    broker.publish("category_created", {"user": username, "category": {"id": db_category.id, "name": db_category.name}})
    return db_category

@app.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db)):
    return db.query(CategoryDB).all()

@app.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(CategoryDB).filter(CategoryDB.id == category_id).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@app.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: int, category: CategoryUpdate, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    db_category = db.query(CategoryDB).filter(CategoryDB.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    db_category.name = category.name
    db.commit()
    db.refresh(db_category)
    broker.publish("category_updated", {"user": username, "category": {"id": db_category.id, "name": db_category.name}})
    return db_category

@app.delete("/categories/{category_id}", response_model=CategoryResponse)
async def delete_category(category_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    db_category = db.query(CategoryDB).filter(CategoryDB.id == category_id).first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    deleted = {"id": db_category.id, "name": db_category.name}
    db.delete(db_category)
    db.commit()
    broker.publish("category_deleted", {"user": username, "category": deleted})
    return deleted

@app.post("/products/{product_id}/categories/{category_id}")
async def register_category(product_id: int, category_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    category = db.query(CategoryDB).filter(CategoryDB.id == category_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category in product.categories:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category already registered for product",
        )

    product.categories.append(category)
    db.commit()
    broker.publish("product_updated", {"user": username, "product": product_to_dict(product)})
    return {"message": "Category registered for product"}

@app.delete("/products/{product_id}/categories/{category_id}")
async def unregister_category(product_id: int, category_id: int, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    category = db.query(CategoryDB).filter(CategoryDB.id == category_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category not in product.categories:
        raise HTTPException(status_code=404, detail="Category not assigned to product")

    product.categories.remove(category)
    db.commit()
    broker.publish("product_updated", {"user": username, "product": product_to_dict(product)})
    return {"message": "Category removed from product"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)