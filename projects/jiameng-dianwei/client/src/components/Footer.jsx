export default function Footer() {
  return (
    <footer className="border-t border-card-border mt-20 py-10">
      <div className="max-w-6xl mx-auto px-4 text-center">
        <div className="flex items-center justify-center gap-2 mb-3">
          <div className="w-6 h-6 bg-primary rounded flex items-center justify-center text-white font-bold text-xs">探</div>
          <span className="text-text-secondary font-medium">探铺</span>
        </div>
        <p className="text-text-muted text-xs mb-2">
          © 2024 探铺. 本平台仅提供数据参考，不构成投资建议。
        </p>
        <p className="text-text-muted text-xs">
          加盟决策风险由用户自行承担，请结合实地考察综合判断。
        </p>
      </div>
    </footer>
  )
}
