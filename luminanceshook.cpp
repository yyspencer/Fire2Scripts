#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <limits>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <boost/math/distributions/students_t.hpp>
#include <numeric>
#include <set>
//output luminance values from shook folder
using namespace std;
namespace fs = filesystem;
using namespace boost::math;
typedef long long ll;
typedef pair<ll, ll> pll;
#define pub push_back
#define mp make_pair
#define pob pop_back
#define X first
#define Y second
const ll INF = 0x3f3f3f3f3f3f3f3f;

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

// Check if a file has a .csv extension
bool isCSVFile(const fs::path& filePath) {
    return filePath.extension() == ".csv";
}

// Load CSV file into a 2D vector
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

// Find the columns for left and right pupil measurements
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

// Find the row indices for the "0.2 seconds" and "shook" events
pair<int, int> findEventRows(const vector<vector<string>>& data, int eventColumn) {
    int rowFor02 = -1, rowForShook = -1;
    for (size_t i = 1; i < data.size(); i++) { // skip header
        if (data[i].size() <= eventColumn) continue;
        string eventColumnValue = data[i][eventColumn];

        if (eventColumnValue.find("0.2 seconds") != string::npos && rowFor02 == -1) {
            rowFor02 = i;
        }
        if (eventColumnValue.find("shook") != string::npos && rowForShook == -1) {
            rowForShook = i;
        }
        if (rowFor02 != -1 && rowForShook != -1) break;
    }
    return {rowFor02, rowForShook};
}

int main() {
    ios_base::sync_with_stdio(0);
    cin.tie(0);

    string path = ".";
    fs::path shookFolder = fs::path(path) / "shook";
    fs::path luminanceFolder = fs::path(path) / "luminance";

    // Create the luminance folder if it doesn't exist
    if (!fs::exists(luminanceFolder)) {
        fs::create_directory(luminanceFolder);
    }

    cout << "Scanning CSV files in the shook folder..." << endl;
    if (!fs::exists(shookFolder) || !fs::is_directory(shookFolder)) {
        cerr << "Error: 'shook' folder does not exist!" << endl;
        return 1;
    }

    // Process each CSV file in the shook folder
    for (const auto& entry : fs::directory_iterator(shookFolder)) {
        if (fs::is_regular_file(entry.path()) && isCSVFile(entry.path())) {
            string fileName = entry.path().filename().string();
            // The file index is the first 5 characters of the filename
            string fileIndex = fileName.substr(0, 5);
            cout << "Extracting luminance level of file " << fileIndex << endl;

            // Load CSV file data
            vector<vector<string>> data = loadCSV(entry.path().string());
            if (data.empty()) {
                cout << "Index " << fileIndex << " -> ERROR: Could not load CSV ❌" << endl;
                continue;
            }

            // Find pupil columns and determine luminance column (leftPupilCol - 1)
            pair<int, int> pupilColumns = findPupilColumns(data[0]);
            if (pupilColumns.first == -1 || pupilColumns.second == -1) {
                cout << "Index " << fileIndex << " -> ERROR: 'leftPupil' or 'rightPupil' column not found ❌" << endl;
                continue;
            }
            int luminanceCol = pupilColumns.first - 1;

            // Find the event column (assumed to contain "robotEvent")
            int eventColumn = -1;
            for (size_t i = 0; i < data[0].size(); i++) {
                if (trim(data[0][i]).find("robotEvent") != string::npos) {
                    eventColumn = i;
                    break;
                }
            }
            if (eventColumn == -1) {
                cout << "Index " << fileIndex << " -> ERROR: 'robotEvent' column not found ❌" << endl;
                continue;
            }

            // Locate the rows for the "0.2 seconds" and "shook" events
            pair<int, int> eventRows = findEventRows(data, eventColumn);
            if (eventRows.first == -1 || eventRows.second == -1) {
                cout << "Index " << fileIndex << " -> ERROR: '0.2 seconds' or 'shook' event not found ❌" << endl;
                continue;
            }

            // Extract the time values for events (assumed to be in column 0)
            double beforeTime = stod(data[eventRows.first][0]); // time at "0.2 seconds"
            double afterTime = stod(data[eventRows.second][0]);   // time at "shook"

            vector<double> luminanceBefore;
            vector<double> luminanceAfter;

            // Iterate through data rows (skip header)
            for (size_t i = 1; i < data.size(); i++) {
                if (data[i].size() <= (unsigned)max(luminanceCol, 0))
                    continue;
                double timeValue, luminance;
                try {
                    timeValue = stod(data[i][0]);
                    luminance = stod(data[i][luminanceCol]);
                } catch (...) {
                    continue;
                }

                // Exclude invalid luminance values
                if (luminance == -1)
                    continue;

                // Collect luminance values for the before window (5 seconds before "0.2 seconds")
                if (timeValue >= (beforeTime - 5.0) && timeValue <= beforeTime) {
                    luminanceBefore.pub(luminance);
                }
                // Collect luminance values for the after window (5 seconds after "shook")
                if (timeValue >= afterTime && timeValue <= (afterTime + 5.0)) {
                    luminanceAfter.pub(luminance);
                }
            }

            // Build the output file name: index+luminance.txt in the luminance folder
            string outFileName = (luminanceFolder / (fileIndex + "luminance.txt")).string();
            ofstream outFile(outFileName);
            if (!outFile) {
                cerr << "Error: Could not open file " << outFileName << " for writing." << endl;
                continue;
            }

            // Write all before-window luminance values (one per line)
            for (auto val : luminanceBefore) {
                outFile << val << "\n";
            }
            // Write an empty line to separate the two windows
            outFile << "\n";
            // Write all after-window luminance values (one per line)
            for (auto val : luminanceAfter) {
                outFile << val << "\n";
            }
            outFile.close();
            cout << "Finished processing file " << fileIndex << endl;
        }
    }
    
    cout << "Luminance extraction complete." << endl;
    return 0;
}