export { PageHeader };


function PageHeader({ icon: Icon, title, subtitle }) {
 return (
 <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
 <div>
 <div className="mb-2 flex items-center gap-2 text-brand-hover">
 <Icon size={20} />
 {/* Product name, deliberately not translated: `Dhrishti` is the
     portal's own title, not prose. */}
 <span className="text-xs font-bold uppercase tracking-widest">
 Dhrishti
 </span>
 </div>

 <h2 className="text-2xl font-bold tracking-tight text-fg">
 {title}
 </h2>

 <p className="mt-1 text-sm text-fg-3">{subtitle}</p>
 </div>
 </div>
 );
}
