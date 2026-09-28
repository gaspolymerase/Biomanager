import SwiftUI

/// BioManager for iPhone and iPad: a companion for the lab's BioManager server.
/// The first launch asks for the server's address; after that it opens straight
/// into BioManager. Change server, on the screen shown when the server
/// cannot be reached, points it somewhere else.
@main
struct BioManagerApp: App {
    @State private var server: URL? = Server.saved

    var body: some Scene {
        WindowGroup {
            Group {
                if let server {
                    MainView(server: server) { self.server = nil }
                        .id(server)   // a new server starts a fresh page
                } else {
                    SetupView { self.server = $0 }
                }
            }
            .tint(Color.accentColor)
        }
    }
}
