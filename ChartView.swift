import SwiftUI
import Charts

struct ChartView: View {
  let categories: [Category]
  let onCategorySelected: (Category) -> Void

  private let minPercentageForOverlay: Double = 0.1

  private var totalAmount: Double {
	categories.reduce(0) { $0 + $1.amount }
  }

  private var smallCategories: [Category] {
	categories.filter { $0.amount / totalAmount < minPercentageForOverlay }
  }

  var body: some View {
	VStack {
	  Chart(categories) { category in
		BarMark(
		  x: .value("Amount", category.amount)
		)
		.foregroundStyle(category.color)
        .accessibilityLabel(Text(category.name))
        .accessibilityValue(Text("\(category.amount, specifier: "%.0f")"))
        .accessibilityHint(Text("Double tap to select this category"))
        .accessibilityIdentifier("BarMark_\(category.name)")
        .accessibilityAddTraits(.isButton)
	  }
      .accessibilityElement(children: .contain)
      .accessibilityLabel(Text("Category amounts chart"))
      .accessibilityHint(Text("Bar chart showing the amount for each category. Swipe to explore categories."))
	  .chartPlotStyle { plotArea in
		plotArea
		  .background(Color(.systemFill))
		  .cornerRadius(8)
	  }
	  .chartXScale(domain: 0...totalAmount)
	  .chartXAxis(.hidden)
	  .frame(height: 25)
	  .chartOverlay { proxy in
		GeometryReader { geometry in
		  Rectangle().fill(.clear).contentShape(Rectangle())
			.onTapGesture { location in
			  let plotFrame = geometry[proxy.plotFrame!]
			  let xLocation = location.x - plotFrame.minX
			  guard xLocation >= 0, xLocation <= plotFrame.width else { return }

			  let xValue = proxy.value(atX: xLocation) ?? 0

			  var accumulated: Double = 0
			  for category in categories {
				accumulated += category.amount
				if xValue <= Int(accumulated) {
				  onCategorySelected(category)
				  break
				}
			  }
			}
            .accessibilityHidden(true)
		}
	  }
	}
    .accessibilityElement(children: .contain)
    .accessibilityIdentifier("ChartView_VStack")
  }
}

#Preview {
  ChartView(
	categories: [
	  Category(
		name: "Automotive",
		categoryColor: CategoryColor(r: 255, g: 99, b: 71, alpha: 1.0),
		amount: 1250
	  ),
	  Category(
		name: "Automotive",
		categoryColor: CategoryColor(r: 255, g: 99, b: 71, alpha: 1.0),
		amount: 1250
	  )
	],
	onCategorySelected: { _ in }
  )
}
