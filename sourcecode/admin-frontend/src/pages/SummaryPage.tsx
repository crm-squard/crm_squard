import Alert from "antd/es/alert";
import Card from "antd/es/card";
import Collapse from "antd/es/collapse";
import DatePicker from "antd/es/date-picker";
import Empty from "antd/es/empty";
import Tag from "antd/es/tag";
import Typography from "antd/es/typography";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import AdminPageLayout from "../components/AdminPageLayout";
import CardLoading from "../components/CardLoading";
import { useAuth } from "../auth/AuthContext";
import { getDailySummary, type DailySummary } from "../api/summary";
import { ui } from "../uiStyles";

const { Paragraph, Title } = Typography;

/** 常見主題次數長條圖：純 CSS 呈現，資料量小（通常個位數~十幾個主題），不需要另外引入圖表套件。 */
function CategoryChart({
  categories,
}: {
  categories: DailySummary["categories"];
}) {
  if (categories.length === 0) return null;
  const sorted = [...categories].sort((a, b) => b.count - a.count);
  const max = Math.max(...sorted.map((c) => c.count), 1);
  return (
    <div className={ui.summaryChart}>
      {sorted.map((category) => (
        <div key={category.name} className={ui.summaryChartRow}>
          <span className={ui.summaryChartLabel} title={category.name}>
            {category.name}
          </span>
          <span className={ui.summaryChartTrack}>
            <span
              className={ui.summaryChartBar}
              style={{ width: `${(category.count / max) * 100}%` }}
            />
          </span>
          <span className={ui.summaryChartCount}>{category.count}</span>
        </div>
      ))}
    </div>
  );
}

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
          <CardLoading label="客服摘要讀取中" />
        ) : error ? (
          <Alert type="error" showIcon message={error} />
        ) : data ? (
          data.question_count === 0 ? (
            <Empty description="這天沒有使用者提問紀錄" />
          ) : (
            <>
              <Tag color="blue">{data.question_count} 則提問</Tag>
              <CategoryChart categories={data.categories} />
              <Paragraph className={ui.preWrap}>{data.summary}</Paragraph>

              {data.needs_merchant_attention.length > 0 && (
                <div className={ui.summaryAttentionSection}>
                  <Title className={ui.summaryAttentionTitle} level={5}>
                    需商家關注（{data.needs_merchant_attention.length}）
                  </Title>
                  <Paragraph
                    className={ui.summaryAttentionDescription}
                    type="secondary"
                  >
                    這些問題與業務相關，但機器人可能答不出來，或太獨特無法歸類，建議人工確認。
                  </Paragraph>
                  <ul className={ui.summaryAttentionList}>
                    {data.needs_merchant_attention.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </div>
              )}

              {data.meaningless_questions.length > 0 && (
                <Collapse
                  ghost
                  className={ui.marginTop4}
                  items={[
                    {
                      key: "meaningless",
                      label: `無意義訊息（${data.meaningless_questions.length}）`,
                      children: (
                        <ul className={ui.summaryMeaninglessList}>
                          {data.meaningless_questions.map((q, i) => (
                            <li key={i}>{q}</li>
                          ))}
                        </ul>
                      ),
                    },
                  ]}
                />
              )}
            </>
          )
        ) : null}
      </Card>
    </AdminPageLayout>
  );
}
