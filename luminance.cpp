#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <cmath>
#include <string>

using namespace std;
namespace fs = std::filesystem;
//just calculating the luminance values
// Function to compute average and sample variance for a vector of doubles.
void computeStats(const vector<double>& values, double &avg, double &variance) {
    if (values.empty()) {
        avg = 0;
        variance = 0;
        return;
    }
    double sum = 0, sumSq = 0;
    for (double v : values) {
        sum += v;
        sumSq += v * v;
    }
    size_t n = values.size();
    avg = sum / n;
    if (n > 1)
        variance = (sumSq - (sum * sum) / n) / (n - 1);
    else
        variance = 0;
}

int main() {
    fs::path luminanceFolder = fs::path(".") / "luminance";
    if (!fs::exists(luminanceFolder) || !fs::is_directory(luminanceFolder)) {
        cerr << "Error: 'luminance' folder does not exist in the current directory." << endl;
        return 1;
    }
    
    // Global vectors to store all luminance values from before and after sections.
    vector<double> globalBefore;
    vector<double> globalAfter;
    
    // Iterate over all txt files in the "luminance" folder.
    for (const auto& entry : fs::directory_iterator(luminanceFolder)) {
        if (fs::is_regular_file(entry.path()) && entry.path().extension() == ".txt") {
            ifstream inFile(entry.path());
            if (!inFile) {
                cerr << "Error: Could not open file " << entry.path() << endl;
                continue;
            }
            cout << "Processing file: " << entry.path().filename().string() << endl;
            
            string line;
            bool readingBefore = true;
            while (getline(inFile, line)) {
                // Trim the line (optional; assuming no extra spaces)
                if (line.find_first_not_of(" \t\r\n") == string::npos) {
                    // Empty line indicates separation between before and after.
                    readingBefore = false;
                    continue;
                }
                try {
                    double val = stod(line);
                    if (readingBefore)
                        globalBefore.push_back(val);
                    else
                        globalAfter.push_back(val);
                } catch (...) {
                    // If conversion fails, skip this line.
                    continue;
                }
            }
            inFile.close();
        }
    }
    
    // Compute statistics for both sections.
    double avgBefore, varBefore, avgAfter, varAfter;
    computeStats(globalBefore, avgBefore, varBefore);
    computeStats(globalAfter, avgAfter, varAfter);
    
    // Print the final results to the console.
    cout << "\nAggregated Luminance Statistics:" << endl;
    cout << "Before:" << endl;
    cout << "  Average luminance: " << avgBefore << endl;
    cout << "  Variance: " << varBefore << endl;
    
    cout << "After:" << endl;
    cout << "  Average luminance: " << avgAfter << endl;
    cout << "  Variance: " << varAfter << endl;
    
    return 0;
}