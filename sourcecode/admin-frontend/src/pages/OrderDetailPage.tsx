import ArrowLeftOutlined from "@ant-design/icons/ArrowLeftOutlined";
import Alert from "antd/es/alert";
import Button from "antd/es/button";
import Descriptions from "antd/es/descriptions";
import Result from "antd/es/result";
import Skeleton from "antd/es/skeleton";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getOrder, OrderApiError } from "../api/orders";
import StatusTag from "../components/StatusTag";
import type { AdminOrder } from "../types/order";

const moneyFormatter = new Intl.NumberFormat("zh-TW", { style: "currency", currency: "TWD", maximumFractionDigits: 0 });

export default function OrderDetailPage() {
  const navigate = useNavigate();
  const { orderId = "" } = useParams();
  const [order, setOrder] = useState<AdminOrder | null>(null);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    getOrder(orderId, controller.signal)
      .then(setOrder)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError({ message: reason instanceof Error ? reason.message : "無法取得訂單資料。", status: reason instanceof OrderApiError ? reason.status : undefined });
      });
    return () => controller.abort();
  }, [orderId]);

  if (error?.status === 404) return <Result status="404" title="找不到訂單" subTitle={error.message} extra={<Button type="primary" onClick={() => navigate("/orders")}>返回訂單列表</Button>} />;

  return (
    <main>
      <div className="page-heading detail-heading"><div><Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/orders")}>返回訂單列表</Button><h1>訂單詳情</h1><p>{order?.NewOrderID || orderId}</p></div>{order && <StatusTag status={order.Status} />}</div>
      <section className="surface detail-surface">
        {error ? <Alert type="error" showIcon message={error.message} /> : !order ? <Skeleton active paragraph={{ rows: 8 }} /> : (
          <>
            <h2>訂單資訊</h2>
            <Descriptions bordered column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="訂單編號">{order.NewOrderID || order.id}</Descriptions.Item>
              <Descriptions.Item label="原始編號">{order.OrderID}</Descriptions.Item>
              <Descriptions.Item label="訂單日期">{order.OrderDate}</Descriptions.Item>
              <Descriptions.Item label="付款方式">{order.PaymentMethod}</Descriptions.Item>
              <Descriptions.Item label="折扣">{order.Discount}</Descriptions.Item>
              <Descriptions.Item label="訂單金額">{moneyFormatter.format(order.OrderValue)}</Descriptions.Item>
            </Descriptions>
            <h2>商品資訊</h2>
            <Descriptions bordered column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="商品編號">{order.ProductID}</Descriptions.Item>
              <Descriptions.Item label="商品名稱">{order.ProductName}</Descriptions.Item>
              <Descriptions.Item label="分類">{order.Category}</Descriptions.Item>
              <Descriptions.Item label="數量">{order.Quantity}</Descriptions.Item>
              <Descriptions.Item label="單價">{moneyFormatter.format(order.UnitPrice)}</Descriptions.Item>
              <Descriptions.Item label="銷售金額">{moneyFormatter.format(order.Sales)}</Descriptions.Item>
            </Descriptions>
            <h2>顧客資訊</h2>
            <Descriptions bordered column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="顧客編號">{order.CustomerID}</Descriptions.Item>
              <Descriptions.Item label="電話">{order.PhoneNumber}</Descriptions.Item>
              <Descriptions.Item label="城市">{order.City}</Descriptions.Item>
              <Descriptions.Item label="顧客分群">{order.CustomerSegment}</Descriptions.Item>
              <Descriptions.Item label="年齡">{order.Age}</Descriptions.Item>
              <Descriptions.Item label="加入日期">{order.SignupDate}</Descriptions.Item>
            </Descriptions>
          </>
        )}
      </section>
    </main>
  );
}
