import Alert from "antd/es/alert";
import Button from "antd/es/button";
import OrderTable from "../components/OrderTable";
import { useOrders } from "../hooks/useOrders";
import { ui } from "../uiStyles";
import { tw } from "../utils/tw";

export default function OrdersPage() {
  const { orders, isLoading, error, reload } = useOrders();
  return (
    <main>
      <div className={ui.pageHeading}>
        <div>
          <h1>訂單管理</h1>
          <p>查看前台送出的購物訂單與處理狀態。</p>
        </div>
      </div>
      <section className={tw(ui.surface, ui.ordersSurface)}>
        {error ? (
          <Alert
            type="error"
            showIcon
            message={error}
            action={
              <Button size="small" onClick={reload}>
                重新載入
              </Button>
            }
          />
        ) : (
          <OrderTable orders={orders} loading={isLoading} />
        )}
      </section>
    </main>
  );
}
