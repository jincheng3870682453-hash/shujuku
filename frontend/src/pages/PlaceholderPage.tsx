import { Card, Typography, Result } from 'antd';

const { Title } = Typography;

interface PlaceholderPageProps {
  title: string;
}

function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <Card className="glass-card">
      <Result
        status="info"
        title={<Title level={4}>{title}</Title>}
        subTitle="此功能正在开发中，敬请期待…"
      />
    </Card>
  );
}

export default PlaceholderPage;