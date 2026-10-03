import { PageHeader } from "./PageHeader";

export { IntelligencePanel };


function IntelligencePanel({ title, icon: Icon, subtitle, children }) {
 return (
 <div className="space-y-6">
 <PageHeader icon={Icon} title={title} subtitle={subtitle} />

 {children}
 </div>
 );
}
