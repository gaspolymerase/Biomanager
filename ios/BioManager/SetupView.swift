import SwiftUI

/// Asks for the lab server's address and checks it is a BioManager server before saving it.
struct SetupView: View {
    var onConnected: (URL) -> Void

    @State private var address = Server.saved?.absoluteString ?? ""
    @State private var checking = false
    @State private var problem: String?
    @FocusState private var focused: Bool

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                Image("Logo")
                    .resizable()
                    .frame(width: 88, height: 88)
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .padding(.top, 48)
                    .accessibilityHidden(true)

                Text("Connect to your lab")
                    .font(.title.bold())

                Text("BioManager on your iPhone opens your lab's BioManager server. Ask your lab's BioManager admin for its address.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                TextField("biomanager.example.edu", text: $address)
                    .textContentType(.URL)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.go)
                    .focused($focused)
                    .onSubmit(connect)
                    .padding(.horizontal, 14)
                    .frame(height: 50)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
                    .padding(.top, 8)

                if let problem {
                    Text(problem)
                        .font(.footnote)
                        .foregroundStyle(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Button(action: connect) {
                    HStack {
                        if checking { ProgressView().tint(.white) }
                        Text(checking ? "Checking…" : "Connect").bold()
                    }
                    .frame(maxWidth: .infinity, minHeight: 50)
                }
                .buttonStyle(.borderedProminent)
                .buttonBorderShape(.capsule)
                .disabled(checking)

                Text("Using the BioManager desktop app on your own computer? That copy only works on that computer. To use your phone too, your lab needs a BioManager server.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.top, 24)
            }
            .padding(.horizontal, 28)
            .frame(maxWidth: 520)
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.interactively)
        .onAppear { focused = true }
    }

    private func connect() {
        guard !checking else { return }  // Return and the button can both arrive
        guard let url = Server.normalise(address) else {
            problem = "Type your lab server's address."
            return
        }
        problem = nil
        checking = true
        Task {
            do {
                try await Server.probe(url)
                Server.saved = url
                checking = false
                onConnected(url)
            } catch {
                checking = false
                problem = error.localizedDescription
            }
        }
    }
}
