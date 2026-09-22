import Alert from "antd/es/alert";
import Card from "antd/es/card";
import DatePicker from "antd/es/date-picker";
import Empty from "antd/es/empty";
import Spin from "antd/es/spin";
import Tag from "antd/es/tag";
import Typography from "antd/es/typography";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import AdminPageLayout from "../components/AdminPageLayout";
import { useAuth } from "../auth/AuthContext";
import { getDailySummary, type DailySummary } from "../api/summary";
import { ui } from "../uiStyles";

const { Paragraph } = Typography;

/**
 * 客服摘要：當日提問主題摘要（對應儀表板「今日對話」卡片原本寫的「對話分析功能規劃中」）。
 * 依 AuthContext.selectedChatbotId 過濾，跟 RAG 頁面一樣的模式——切換公司時這裡也要
 * 重新拉取，只看得到目前選定公司的顧客提問內容。
 */
export default function SummaryPage() {
  const { token, selectedChatbotId } = useAuth();
  const [date, setDate] = useState<Dayjs>(() => dayjs());
  const [data, setData] = useState<DailySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !selectedChatbotId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDailySummary(token, selectedChatbotId, date.format("YYYY-MM-DD"))
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "讀取摘要失敗");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, selectedChatbotId, date]);

  return (
    <AdminPageLayout
      title="客服摘要"
      description="查看指定日期使用者向聊天機器人提問的主題摘要。"
      headerExtra={
        <DatePicker
          value={date}
          onChange={(value) => value && setDate(value)}
          allowClear={false}
          disabledDate={(current) => current && current > dayjs().endOf("day")}
        />
      }
    >
      <Card>
        {loading ? (
          <Spin />
        ) : error ? (
          <Alert type="error" showIcon message={error} />
        ) : data ? (
          data.question_count === 0 ? (
            <Empty description="這天沒有使用者提問紀錄" />
          ) : (
            <>
              <Tag color="blue">{data.question_count} 則提問</Tag>
              <Paragraph className={ui.preWrap}>{data.summary}</Paragraph>
            </>
          )
        ) : null}
      </Card>
    </AdminPageLayout>
  );
}
