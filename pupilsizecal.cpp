//this calculates the actual aggregate & per person pupil size for the exported files
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <limits>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <set>
#include <utility>

using namespace std;
namespace fs = filesystem;
typedef long long ll;
typedef pair<ll, ll> pll;
#define pub push_back
#define mp make_pair
#define pob pop_back
#define X first
#define Y second
const ll INF = 0x3f3f3f3f3f3f3f3f;

// Function to trim whitespace from a string
string trim(const string& str) {
    string trimmed = str;
    trimmed.erase(trimmed.begin(), find_if(trimmed.begin(), trimmed.end(), [](unsigned char ch) {
        return !isspace(ch);
    }));
    trimmed.erase(find_if(trimmed.rbegin(), trimmed.rend(), [](unsigned char ch) {
        return !isspace(ch);
    }).base(), trimmed.end());
    return trimmed;
}

// Function to check if a file has a .csv extension
bool isCSVFile(const fs::path& filePath) {
    return filePath.extension() == ".csv";
}

// Function to load CSV file into a 2D vector
vector<vector<string>> loadCSV(const string& filePath) {
    vector<vector<string>> data;
    ifstream file(filePath);
    if (!file.is_open()) {
        cerr << "Error: Could not open " << filePath << endl;
        return {};
    }
    string line;
    while (getline(file, line)) {
        stringstream ss(line);
        vector<string> row;
        string cell;
        while (getline(ss, cell, ',')) {
            row.pub(cell);
        }
        data.pub(row);
    }
    file.close();
    return data;
}

// Function to find the columns that contain "leftPupil" and "rightPupil"
pair<int, int> findPupilColumns(const vector<string>& headerRow) {
    int leftPupilCol = -1, rightPupilCol = -1;
    for (size_t i = 0; i < headerRow.size(); i++) {
        string trimmedCell = trim(headerRow[i]);
        if (trimmedCell.find("leftPupil") != string::npos) {
            leftPupilCol = i;
        }
        if (trimmedCell.find("rightPupil") != string::npos) {
            rightPupilCol = i;
        }
    }
    return {leftPupilCol, rightPupilCol};
}

// Function to find the row index that contains the "0.2 seconds" tag
int findEventRow(const vector<vector<string>>& data) {
    for (size_t i = 1; i < data.size(); i++) { // skip header
        for (const string& cell : data[i]) {
            if (cell.find("0.2 seconds") != string::npos) {
                return i;  // Return the first occurrence
            }
        }
    }
    return -1;  // Not found
}

// Structure to hold statistical information
struct Stats {
    double sum = 0.0;
    double sumSq = 0.0;
    int count = 0;
    double minVal = numeric_limits<double>::max();
    double maxVal = numeric_limits<double>::lowest();
};

void updateStats(Stats &stats, double value) {
    // Ignore invalid data points (-1)
    if (value == -1) return;
    stats.sum += value;
    stats.sumSq += value * value;
    stats.count++;
    stats.minVal = min(stats.minVal, value);
    stats.maxVal = max(stats.maxVal, value);
}

void computeAndPrintStats(const string& label, const Stats &stats) {
    if (stats.count == 0) {
        cout << label << ": No valid data." << endl;
        return;
    }
    double avg = stats.sum / stats.count;
    double variance = (stats.count > 1) ? ((stats.sumSq - (stats.sum * stats.sum) / stats.count) / (stats.count - 1)) : 0.0;
    cout << label << endl;
    cout << "  Average: " << avg << endl;
    cout << "  Variance: " << variance << endl;
    cout << "  Min: " << stats.minVal << ", Max: " << stats.maxVal << endl;
}

int main() {
    ios_base::sync_with_stdio(0);
    cin.tie(0);

    // Folder paths for the pupil size files (extracted previously)
    fs::path pupilFolder = fs::path(".") / "pupil size";
    if (!fs::exists(pupilFolder) || !fs::is_directory(pupilFolder)) {
        cerr << "Error: 'pupil size' folder does not exist!" << endl;
        return 1;
    }

    // Global aggregated stats for every data point (across all indices)
    Stats globalLeftBefore, globalRightBefore, globalLeftAfter, globalRightAfter;
    // Per person average stats (each file's average becomes one data point)
    Stats personLeftBefore, personRightBefore, personLeftAfter, personRightAfter;

    // Process each text file in the pupil size folder.
    for (const auto& entry : fs::directory_iterator(pupilFolder)) {
        if (fs::is_regular_file(entry.path()) && entry.path().extension() == ".txt") {
            ifstream inFile(entry.path());
            if (!inFile) {
                cerr << "Error: Could not open file " << entry.path() << endl;
                continue;
            }
            cout << "Processing file: " << entry.path().filename().string() << endl;

            // Vectors to hold data points for this person
            vector<double> fileLeftBefore, fileRightBefore, fileLeftAfter, fileRightAfter;
            
            string line;
            bool isAfterSection = false;
            while (getline(inFile, line)) {
                if (line.find_first_not_of(" \t\r\n") == string::npos) {
                    // Empty line separates before and after sections.
                    isAfterSection = true;
                    continue;
                }
                stringstream ss(line);
                double leftVal, rightVal;
                if (!(ss >> leftVal >> rightVal)) continue;
                
                // Update global stats if valid (ignoring -1)
                if (!isAfterSection) {
                    if (leftVal != -1) updateStats(globalLeftBefore, leftVal);
                    if (rightVal != -1) updateStats(globalRightBefore, rightVal);
                    fileLeftBefore.push_back(leftVal);
                    fileRightBefore.push_back(rightVal);
                } else {
                    if (leftVal != -1) updateStats(globalLeftAfter, leftVal);
                    if (rightVal != -1) updateStats(globalRightAfter, rightVal);
                    fileLeftAfter.push_back(leftVal);
                    fileRightAfter.push_back(rightVal);
                }
            }
            inFile.close();

            // Compute per-person averages for before and after windows.
            // Only include if there is at least one valid data point.
            auto computeFileAvg = [](const vector<double>& vals) -> double {
                double sum = 0.0;
                int count = 0;
                for (double v : vals) {
                    if (v != -1) { sum += v; count++; }
                }
                return (count > 0) ? (sum / count) : -1;
            };

            double fileLeftBeforeAvg = computeFileAvg(fileLeftBefore);
            double fileRightBeforeAvg = computeFileAvg(fileRightBefore);
            double fileLeftAfterAvg = computeFileAvg(fileLeftAfter);
            double fileRightAfterAvg = computeFileAvg(fileRightAfter);

            // Only update per-person stats if the average is valid (not -1)
            if (fileLeftBeforeAvg != -1) updateStats(personLeftBefore, fileLeftBeforeAvg);
            if (fileRightBeforeAvg != -1) updateStats(personRightBefore, fileRightBeforeAvg);
            if (fileLeftAfterAvg != -1) updateStats(personLeftAfter, fileLeftAfterAvg);
            if (fileRightAfterAvg != -1) updateStats(personRightAfter, fileRightAfterAvg);
        }
    }

    // Print aggregated statistics across all data points.
    cout << "\nActual Pupil Size Data \n";
    cout << "Aggregate Pupil Size Statistics (all data points):\n" << endl;
    cout << "Before Event:" << endl;
    computeAndPrintStats("  Left Eye", globalLeftBefore);
    computeAndPrintStats("  Right Eye", globalRightBefore);
    cout << "\nAfter Event:" << endl;
    computeAndPrintStats("  Left Eye", globalLeftAfter);
    computeAndPrintStats("  Right Eye", globalRightAfter);

    // Print per-person averaged statistics (each file's average treated as one data point).
    cout << "\nPer Person Average Pupil Size Statistics (aggregated over indices):\n" << endl;
    cout << "Before Event:" << endl;
    computeAndPrintStats("  Left Eye", personLeftBefore);
    computeAndPrintStats("  Right Eye", personRightBefore);
    cout << "\nAfter Event:" << endl;
    computeAndPrintStats("  Left Eye", personLeftAfter);
    computeAndPrintStats("  Right Eye", personRightAfter);

    return 0;
}