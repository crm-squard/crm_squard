import Alert from "antd/es/alert";
import Card from "antd/es/card";
import DatePicker from "antd/es/date-picker";
import Empty from "antd/es/empty";
import Tag from "antd/es/tag";
import Table from "antd/es/table";
import Typography from "antd/es/typography";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import AdminPageLayout from "../components/AdminPageLayout";
import CardLoading from "../components/CardLoading";
import ChatbotSettingsTabs from "../components/ChatbotSettingsTabs";
import { useAuth } from "../auth/AuthContext";
import { getPeriodSummary, type PeriodSummary } from "../api/summary";
import { ui } from "../uiStyles";

const { Paragraph, Text } = Typography;

function getUtcToday() {
  return dayjs(new Date().toISOString().slice(0, 10));
}

function getWeekRange(date: Dayjs): [Dayjs, Dayjs] {
  const startDate = date.subtract((date.day() + 6) % 7, "day").startOf("day");
  const endDate = startDate.add(6, "day");
  const today = getUtcToday();
  return [startDate, endDate.isAfter(today, "day") ? today : endDate];
}

interface SummaryTableRow {
  key: string;
  label: string;
  content: ReactNode;
}

const summaryColumns: ColumnsType<SummaryTableRow> = [
  {
    title: "摘要欄位",
    dataIndex: "label",
    key: "label",
    width: 180,
  },
  {
    title: "內容",
    dataIndex: "content",
    key: "content",
  },
];

function MessageList({ items }: { items: string[] }) {
  if (items.length === 0) return <Text type="secondary">無</Text>;
  return (
    <ul className={ui.summaryTableList}>
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

/**
 * 客服摘要：指定週期內的提問主題摘要。
 * 依 AuthContext.selectedChatbotId 過濾，跟 RAG 頁面一樣的模式——切換公司時這裡也要
 * 重新拉取，只看得到目前選定公司的顧客提問內容。
 */
export default function SummaryPage() {
  const { token, selectedChatbotId } = useAuth();
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>(() =>
    getWeekRange(getUtcToday()),
  );
  const [data, setData] = useState<PeriodSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !selectedChatbotId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPeriodSummary(
      token,
      selectedChatbotId,
      dateRange[0].format("YYYY-MM-DD"),
      dateRange[1].format("YYYY-MM-DD"),
    )
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
  }, [token, selectedChatbotId, dateRange]);

  if (!selectedChatbotId) return <Navigate to="/chatbots" replace />;

  const summaryRows: SummaryTableRow[] = data
    ? [
        {
          key: "question_count",
          label: "提問數",
          content: <Tag color="blue">{data.question_count} 則提問</Tag>,
        },
        {
          key: "categories",
          label: "常見主題",
          content:
            data.categories.length === 0 ? (
              <Text type="secondary">無可歸納的常見主題</Text>
            ) : (
              <div className={ui.summaryCategoryTags}>
                {[...data.categories]
                  .sort((a, b) => b.count - a.count)
                  .map((category) => (
                    <Tag
                      key={category.name}
                    >{`${category.name}（${category.count}）`}</Tag>
                  ))}
              </div>
            ),
        },
        {
          key: "summary",
          label: "摘要",
          content: (
            <Paragraph className={ui.summaryTableParagraph}>
              {data.summary}
            </Paragraph>
          ),
        },
        {
          key: "needs_merchant_attention",
          label: "需商家關注",
          content: <MessageList items={data.needs_merchant_attention} />,
        },
        {
          key: "meaningless_questions",
          label: "無意義訊息",
          content: <MessageList items={data.meaningless_questions} />,
        },
      ]
    : [];

  return (
    <AdminPageLayout
      title="客服摘要"
      description="查看指定週期內使用者向聊天機器人提問的主題摘要。"
    >
      <ChatbotSettingsTabs />
      <Card className={ui.settingsCard}>
        <div className={ui.summaryPeriodControl}>
          <Text type="secondary">摘要週期（週一至週日）</Text>
          <DatePicker.RangePicker
            aria-label="客服摘要週期"
            allowClear={false}
            disabled={loading}
            disabledDate={(current) =>
              current && current.isAfter(getUtcToday(), "day")
            }
            format="YYYY-MM-DD"
            value={dateRange}
            onCalendarChange={(dates) => {
              const selectedDate = dates?.[0];
              if (selectedDate) setDateRange(getWeekRange(selectedDate));
            }}
          />
        </div>
        {loading ? (
          <CardLoading label="客服摘要讀取中" />
        ) : error ? (
          <Alert type="error" showIcon message={error} />
        ) : data ? (
          data.question_count === 0 ? (
            <Empty description="這個週期沒有使用者提問紀錄" />
          ) : (
            <Table<SummaryTableRow>
              aria-label="客服摘要資料表"
              className={ui.summaryTable}
              columns={summaryColumns}
              dataSource={summaryRows}
              pagination={false}
              rowKey="key"
              size="small"
              tableLayout="fixed"
            />
          )
        ) : null}
      </Card>
    </AdminPageLayout>
  );
}
