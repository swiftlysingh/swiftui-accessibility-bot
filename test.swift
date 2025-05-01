import Foundation
import SwiftUI

@Observable
class HomeViewModel {
  var totalAmount: Double = 0
  var utilization: Double = 0
  var selectedTimeframe: String = "This Month"
  var selectedCategory: Category?
  var currentPage = 0
  var showingTransactionSheet = false
  var showImporting = false

  var categories: [Category] = []
  var notices: [Notice] = []
  var noticesInTabs: [Notice] = []
  var accountSummary: AccountSummary?

  var statement: CreditCardStatement?

  var fileDetails: [FileDetails] = []

  var bounceValue = 0
  var currentNoticeIndex = 0

  let timer = Timer.publish(every: 5, on: .main, in: .common).autoconnect()

  var isViewingTotal = false

  init() {
	loadMockData()
//	getStatementPDFs()
  }

  private func loadMockData() {
	do {
	  statement = try MockDataLoader.loadMockData()
	  processTransactions()
	} catch {
	  print("Error loading mock data: \(error)")
	}
  }

  private func processTransactions() {
	guard let categories = statement?.card.categories else { return }

	self.categories = categories.sorted { first, second in
	  return first.amount > second.amount
	}
	self.notices = statement?.card.notices ?? []
	noticesInTabs = notices.filter({ $0.severity >= 1 })
	totalAmount = statement?.card.transactions.totals.debit ?? 0
	accountSummary = statement?.card.accountSummary
	utilization = (
	  accountSummary!
		.totalDue / (accountSummary?.creditLimit ?? .greatestFiniteMagnitude)
	) * 100
  }

  func selectCategory(_ category: Category) {
	isViewingTotal = false
	selectedCategory = category
	showingTransactionSheet = true
  }

  func addTransaction() {
	showingTransactionSheet = true
  }

  func uploadNewStatements() {
	showImporting = true
  }

  func fileSelectionHandler(result: Result<URL, any Error>) {
	  switch(result) {
		case .success(let fileURL):
		  print(fileURL.absoluteString)
		  guard fileURL.startAccessingSecurityScopedResource() else {
			// Handle error - can't access the resource
			return
		  }

		  // Now you can open and read the file
		  Task {
			do {
			  let data = try Data(contentsOf: fileURL)

			  try await AppWrite.shared
				.uploadPDF(fileData: data, with: fileURL.lastPathComponent)


			} catch {
			  print("Error with file handling: \(error)")
			}
		  }


		case .failure(let error):
		  print("\(error) \n While importing pdf")

	}
  }

  func getStatementPDFs() {
	Task {
	  do {
		fileDetails = try await AppWrite.shared.getPDFs()
	  } catch {
		print("Error getting files: \(error)")
	  }
	}
  }
}
