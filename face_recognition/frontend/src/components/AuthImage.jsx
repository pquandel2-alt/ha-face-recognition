import { useEffect, useState } from 'react'
import api from '../api'

const NO_IMAGE_SRC =
  'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Crect fill="%23333" width="100" height="100"/%3E%3Ctext fill="%23666" text-anchor="middle" dy=".3em" x="50" y="50"%3ENo image%3C/text%3E%3C/svg%3E'

// The API requires a custom Basic-Auth header, so a plain <img src="/api/..."> can't
// authenticate — fetch the bytes via the authenticated axios instance instead and
// render them as an object URL.
export default function AuthImage({ url, className }) {
  const [src, setSrc] = useState(null)

  useEffect(() => {
    let objectUrl
    let cancelled = false
    api
      .get(url, { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(res.data)
        setSrc(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setSrc(NO_IMAGE_SRC)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])

  return <img src={src || NO_IMAGE_SRC} alt="" className={className} />
}
