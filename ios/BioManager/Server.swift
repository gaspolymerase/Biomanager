import Foundation

/// The lab server this phone opens, remembered once it has answered as BioManager.
enum Server {
    private static let key = "server"

    static var saved: URL? {
        get { UserDefaults.standard.string(forKey: key).flatMap(URL.init(string:)) }
        set { UserDefaults.standard.set(newValue?.absoluteString, forKey: key) }
    }

    /// What someone typed, as an address to try: https:// when no scheme was
    /// given, no path, no trailing slash. Nil when it cannot be an address.
    static func normalise(_ typed: String) -> URL? {
        var text = typed.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return nil }
        if !text.contains("://") { text = "https://" + text }
        guard var parts = URLComponents(string: text),
              let scheme = parts.scheme?.lowercased(), ["http", "https"].contains(scheme),
              let host = parts.host, !host.isEmpty else { return nil }
        parts.scheme = scheme
        parts.path = ""
        parts.query = nil
        parts.fragment = nil
        return parts.url
    }

    /// Whether a link belongs to the server, so it opens in the app.
    static func owns(_ link: URL, server: URL) -> Bool {
        link.host?.lowercased() == server.host?.lowercased() && link.port == server.port
    }

    enum ProbeError: LocalizedError {
        case notBioManager, unreachable(URL), certificate, insecure

        var errorDescription: String? {
            switch self {
            case .notBioManager:
                return "That address answered, but it isn't a BioManager server."
            case .unreachable(let url):
                return "Couldn't reach \(url.host ?? url.absoluteString). Check the address, and that your phone is on the lab's network or VPN."
            case .certificate:
                return "This iPhone doesn't trust the server's certificate. If your lab uses its own, install its profile and turn it on in Settings → General → About → Certificate Trust Settings."
            case .insecure:
                return "This address isn't https, and iPhones only allow plain http on the local network. Use the server's https address."
            }
        }
    }

    /// Nil error when the address answers /healthz the way BioManager does.
    static func probe(_ url: URL) async throws {
        var request = URLRequest(url: url.appendingPathComponent("healthz"))
        request.timeoutInterval = 8
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch let error as URLError {
            switch error.code {
            case .serverCertificateUntrusted, .serverCertificateHasBadDate, .serverCertificateNotYetValid,
                 .serverCertificateHasUnknownRoot, .secureConnectionFailed:
                throw ProbeError.certificate
            case .appTransportSecurityRequiresSecureConnection:
                throw ProbeError.insecure
            default:
                throw ProbeError.unreachable(url)
            }
        }
        guard (response as? HTTPURLResponse)?.statusCode == 200,
              String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines) == "ok"
        else { throw ProbeError.notBioManager }
    }
}
