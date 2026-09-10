from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app import crud
from app.firebase_client import get_db
from app.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
    ErrorDetail
)

router = APIRouter(prefix="/Product", tags=["Firebase Product Operations"])

COLLECTION_PRODUCTS = "Product"


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="取得單一產品資料",
    responses={404: {"model": ErrorDetail}, 500: {"model": ErrorDetail}}
)
def get_product(product_id: str):
    """
    依據產品 ID (`product_id` 或 `ProductID`) 查詢單一產品資料。
    - **product_id**: 產品識別碼 (例如: `2001`, `P001`)
    """
    try:
        # 1. 優先嘗試依據 Document ID 取得
        doc = crud.get_document(collection_name=COLLECTION_PRODUCTS, doc_id=product_id)
        if doc:
            return ProductResponse(id=doc.id, **doc.data)

        # 2. 若未依 Document ID 找到，嘗試依據 ProductID 欄位查詢
        db = get_db()
        docs = (
            db.collection(COLLECTION_PRODUCTS)
            .where("ProductID", "==", product_id)
            .limit(1)
            .stream()
        )

        for d in docs:
            raw_data = d.to_dict() or {}
            sanitized_data = crud._sanitize_firestore_data(raw_data)
            return ProductResponse(id=d.id, **sanitized_data)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到 ProductID 或 DocID 為 '{product_id}' 的產品"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"讀取產品資料失敗: {str(e)}"
        )


@router.get(
    "",
    response_model=ProductListResponse,
    summary="分頁查詢產品列表",
    responses={500: {"model": ErrorDetail}}
)
def list_products(
    pidx: int = Query(1, ge=1, description="頁碼 (從 1 開始)"),
    pno: int = Query(10, ge=1, le=500, description="每頁筆數 (1-500)")
):
    """
    分頁取得產品列表。
    - **pidx**: 第幾頁 (預設 1)
    - **pno**: 每頁幾筆 (預設 10)
    """
    try:
        offset = (pidx - 1) * pno
        raw_res = crud.list_documents(
            collection_name=COLLECTION_PRODUCTS,
            limit=pno,
            offset=offset
        )

        products_list = [
            ProductResponse(id=doc.id, **doc.data)
            for doc in raw_res.documents
        ]

        return ProductListResponse(
            pidx=pidx,
            pno=pno,
            count=len(products_list),
            products=products_list
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分頁查詢產品列表失敗: {str(e)}"
        )


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增產品資料",
    responses={500: {"model": ErrorDetail}}
)
def create_product(payload: ProductCreate):
    """
    新增一筆產品資料至 Firebase Firestore `Product` 集合中。
    - 所有欄位均為字串 (`ProductID`, `ProductNameZH`, `ProductNameEN`, `Category`, `Description`, `DescriptionShort`)。
    """
    try:
        doc_id = payload.ProductID
        product_dict = payload.model_dump()

        res = crud.create_document(
            collection_name=COLLECTION_PRODUCTS,
            data=product_dict,
            doc_id=doc_id
        )

        return ProductResponse(id=res.id, **res.data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"新增產品資料失敗: {str(e)}"
        )


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="更新產品資料",
    responses={404: {"model": ErrorDetail}, 500: {"model": ErrorDetail}}
)
def update_product(product_id: str, payload: ProductUpdate):
    """
    部分增量更新既有產品資料。
    """
    try:
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未傳遞任何需要更新的欄位"
            )

        res = crud.update_document(
            collection_name=COLLECTION_PRODUCTS,
            doc_id=product_id,
            data=update_data,
            merge=True
        )

        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到 ID 為 '{product_id}' 的產品"
            )

        return ProductResponse(id=res.id, **res.data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新產品資料失敗: {str(e)}"
        )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="刪除產品資料",
    responses={404: {"model": ErrorDetail}, 500: {"model": ErrorDetail}}
)
def delete_product(product_id: str):
    """
    刪除指定 ID 的產品資料。
    """
    try:
        success = crud.delete_document(collection_name=COLLECTION_PRODUCTS, doc_id=product_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到要刪除的產品 ID '{product_id}'"
            )
        return {
            "status": "success",
            "message": f"已成功刪除產品 ID '{product_id}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刪除產品資料失敗: {str(e)}"
        )
