//gets all datapoints mapped to a single txt file for noshook files
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

int main() {
    ios_base::sync_with_stdio(0);
    cin.tie(0);

    // Define folder paths
    string path = ".";
    fs::path noshookFolder = fs::path(path) / "noshook";
    fs::path pupilFolder = fs::path(path) / "pupil size";

    // Create the "pupil size" folder if it doesn't exist
    if (!fs::exists(pupilFolder)) {
        fs::create_directory(pupilFolder);
    }

    cout << "Scanning CSV files in the noshook folder..." << endl;
    if (!fs::exists(noshookFolder) || !fs::is_directory(noshookFolder)) {
        cerr << "Error: 'noshook' folder does not exist!" << endl;
        return 1;
    }

    // Process each CSV file in the noshook folder
    for (const auto& entry : fs::directory_iterator(noshookFolder)) {
        if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
            string fileName = entry.path().filename().string();
            // Extract the file index (first 5 characters)
            string fileIndex = fileName.substr(0, 5);
            cout << "Extracting pupil size data for file " << fileIndex << endl;

            // Load CSV file data
            vector<vector<string>> data = loadCSV(entry.path().string());
            if (data.empty()) {
                cout << "Index " << fileIndex << " -> ERROR: Could not load CSV ❌" << endl;
                continue;
            }

            // Find the pupil columns for left and right pupil sizes
            pair<int, int> pupilColumns = findPupilColumns(data[0]);
            if (pupilColumns.first == -1 || pupilColumns.second == -1) {
                cout << "Index " << fileIndex << " -> ERROR: 'leftPupil' or 'rightPupil' column not found ❌" << endl;
                continue;
            }

            // Find the event row using the "0.2 seconds" tag
            int eventRow = findEventRow(data);
            if (eventRow == -1) {
                cout << "Index " << fileIndex << " -> ERROR: '0.2 seconds' tag not found ❌" << endl;
                continue;
            }

            // Extract the time from the event row (assumed to be in column 0)
            double beforeTime = 0.0;
            try {
                beforeTime = stod(data[eventRow][0]);
            } catch (...) {
                cout << "Index " << fileIndex << " -> ERROR: Invalid time value in event row ❌" << endl;
                continue;
            }
            // Estimate event time as 0.229 seconds after the "0.2 seconds" tag
            double eventTime = beforeTime + 0.229;

            // Vectors to store pairs of pupil sizes (left, right)
            vector<pair<double, double>> pupilBefore;
            vector<pair<double, double>> pupilAfter;

            // Iterate through data rows (skip header)
            for (size_t i = 1; i < data.size(); i++) {
                if (data[i].size() <= (unsigned)max(pupilColumns.first, pupilColumns.second))
                    continue;
                double timeValue, leftPupil, rightPupil;
                try {
                    timeValue = stod(data[i][0]);
                    leftPupil = stod(data[i][pupilColumns.first]);
                    rightPupil = stod(data[i][pupilColumns.second]);
                } catch (...) {
                    continue;
                }
                // Do not filter out invalid values; if a value is -1, keep it.
                // Determine which window the data point falls into:
                // Before window: time between (beforeTime - 5.0) and beforeTime
                if (timeValue >= (beforeTime - 5.0) && timeValue <= beforeTime) {
                    pupilBefore.pub({leftPupil, rightPupil});
                }
                // After window: time between eventTime and (eventTime + 5.0)
                if (timeValue >= eventTime && timeValue <= (eventTime + 5.0)) {
                    pupilAfter.pub({leftPupil, rightPupil});
                }
            }

            // Build the output file name: index + "pupil.txt" in the "pupil size" folder
            string outFileName = (pupilFolder / (fileIndex + "pupil.txt")).string();
            ofstream outFile(outFileName);
            if (!outFile) {
                cerr << "Error: Could not open file " << outFileName << " for writing." << endl;
                continue;
            }

            // Write each data point from the before window (one pair per line)
            for (const auto& pairVal : pupilBefore) {
                outFile << pairVal.first << " " << pairVal.second << "\n";
            }
            // Write an empty line to separate before and after data
            outFile << "\n";
            // Write each data point from the after window (one pair per line)
            for (const auto& pairVal : pupilAfter) {
                outFile << pairVal.first << " " << pairVal.second << "\n";
            }
            outFile.close();
            cout << "Finished processing file " << fileIndex << endl;
        }
    }

    cout << "Pupil size extraction complete." << endl;
    return 0;
}