import DatabaseOutlined from "@ant-design/icons/DatabaseOutlined";
import Empty from "antd/es/empty";

export default function RagPage() {
  return (
    <main>
      <div className="page-heading"><div><h1>RAG 知識庫</h1><p>管理 AI 客服使用的專屬知識文件。</p></div></div>
      <section className="surface rag-placeholder">
        <Empty image={<DatabaseOutlined />} description={<><strong>知識庫管理功能規劃中</strong><span>未來將提供文件上傳、索引狀態與重建管理。</span></>} />
      </section>
    </main>
  );
}
