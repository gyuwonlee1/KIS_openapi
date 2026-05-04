import { validatePortfolio } from "./portfolio.js";
import { validateSymbolsInPortfolio } from "./symbols.js";

export function validatePortfolioForSave(portfolio) {
  return [...validatePortfolio(portfolio), ...validateSymbolsInPortfolio(portfolio)];
}
