import { APP_NAME } from '../../config/constants'

export default function Footer() {
  return (
    <footer className="bg-white border-t border-gray-100 py-6 mt-12">
      <div className="max-w-6xl mx-auto px-4 text-center text-sm text-text-sub">
        <p>© 2026 {APP_NAME} · 数据仅供参考，不构成投资建议</p>
        <p className="mt-1">浙ICP备XXXXXXXX号</p>
      </div>
    </footer>
  )
}
