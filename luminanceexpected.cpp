// This code aggregates expected pupil sizes by mapping raw luminance values 
// (using calibration data) to expected pupil sizes. It then computes and prints 
// both aggregate statistics (all data points) and per person averaged statistics.

#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <filesystem>
#include <string>
#include <cmath>
#include <limits>
#include <algorithm>

using namespace std;
namespace fs = std::filesystem;

// Structure to hold a row from the mapping file.
struct MappingRow {
    double luminance;
    double avgLeft;
    int countLeft;
    double stdDevLeft;
    double avgRight;
    int countRight;
    double stdDevRight;
};

// Helper function: Trim whitespace from a string.
string trim(const string &str) {
    string s = str;
    s.erase(s.begin(), find_if(s.begin(), s.end(), [](unsigned char ch) {
        return !isspace(ch);
    }));
    s.erase(find_if(s.rbegin(), s.rend(), [](unsigned char ch) {
        return !isspace(ch);
    }).base(), s.end());
    return s;
}

// Read a mapping file and return a vector of MappingRow.
// Assumes the file is space-separated and the first row is a header.
vector<MappingRow> readMappingFile(const string &filepath) {
    vector<MappingRow> mapping;
    ifstream inFile(filepath);
    if (!inFile) {
        cerr << "Error: Could not open mapping file " << filepath << endl;
        return mapping;
    }
    
    string line;
    bool headerSkipped = false;
    while (getline(inFile, line)) {
        line = trim(line);
        if (line.empty()) continue;
        if (!headerSkipped) { // Skip header
            headerSkipped = true;
            continue;
        }
        istringstream iss(line);
        MappingRow row;
        if (!(iss >> row.luminance >> row.avgLeft >> row.countLeft >> row.stdDevLeft 
                  >> row.avgRight >> row.countRight >> row.stdDevRight))
            continue;
        mapping.push_back(row);
    }
    inFile.close();
    return mapping;
}

// Find the mapping row with the closest luminance value.
MappingRow findClosestMapping(const vector<MappingRow>& mapping, double lum) {
    MappingRow best{};
    double bestDiff = numeric_limits<double>::max();
    for (const auto& row : mapping) {
        double diff = fabs(row.luminance - lum);
        if (diff < bestDiff) {
            bestDiff = diff;
            best = row;
        }
    }
    return best;
}

// Read a luminance file and separate the values into before and after windows.
// The file is assumed to have one luminance value per line, with an empty line separating the two sections.
void readLuminanceFile(const string &filepath, vector<double> &before, vector<double> &after) {
    ifstream inFile(filepath);
    if (!inFile) {
        cerr << "Error: Could not open luminance file " << filepath << endl;
        return;
    }
    string line;
    bool isAfter = false;
    while (getline(inFile, line)) {
        line = trim(line);
        if (line.empty()) { // Empty line separates sections.
            isAfter = true;
            continue;
        }
        try {
            double val = stod(line);
            if (!isAfter)
                before.push_back(val);
            else
                after.push_back(val);
        } catch (...) {
            continue;
        }
    }
    inFile.close();
}

// Structure to accumulate statistical data.
struct Stats {
    double sum = 0.0;
    double sumSq = 0.0;
    int count = 0;
    double minVal = numeric_limits<double>::max();
    double maxVal = numeric_limits<double>::lowest();
};

// Update stats with a value (ignore -1).
void updateStats(Stats &s, double value) {
    if (value == -1) return; // Ignore invalid data.
    s.sum += value;
    s.sumSq += value * value;
    s.count++;
    s.minVal = min(s.minVal, value);
    s.maxVal = max(s.maxVal, value);
}

// Compute mean and variance (using Bessel's correction) from Stats.
pair<double, double> computeMeanVariance(const Stats &s) {
    if (s.count == 0) return {0.0, 0.0};
    double mean = s.sum / s.count;
    double var = (s.count > 1) ? ((s.sumSq - (s.sum * s.sum) / s.count) / (s.count - 1)) : 0.0;
    return {mean, var};
}

// Print stats with the given label.
void printStats(const string &label, const Stats &s) {
    auto [mean, var] = computeMeanVariance(s);
    cout << "  " << label << "\n";
    cout << "    Average: " << mean << "\n";
    cout << "    Variance: " << var << "\n";
    cout << "    Min: " << s.minVal << ", Max: " << s.maxVal << "\n";
}

int main() {
    // Global vectors: expected pupil sizes from each mapping conversion across all files.
    vector<double> globalLeftBefore, globalLeftAfter;
    vector<double> globalRightBefore, globalRightAfter;
    
    fs::path luminanceFolder = fs::path(".") / "luminance";
    fs::path mappingFolder = fs::path(".") / "output_mappings";
    
    if (!fs::exists(luminanceFolder) || !fs::is_directory(luminanceFolder)) {
        cerr << "Error: 'luminance' folder does not exist!" << endl;
        return 1;
    }
    
    // For per person (file) averages.
    vector<double> perPersonLeftBefore, perPersonRightBefore;
    vector<double> perPersonLeftAfter, perPersonRightAfter;
    
    // Process each luminance file.
    for (const auto& entry : fs::directory_iterator(luminanceFolder)) {
        if (!fs::is_regular_file(entry.path()))
            continue;
        string filename = entry.path().filename().string();
        if (filename.size() < 5) continue;
        string index = filename.substr(0, 5);
        cout << "Processing luminance file for index " << index << "..." << endl;
        
        // Construct mapping file path.
        string mappingFilename = index + "_luminance_mapping.txt";
        fs::path mappingPath = mappingFolder / mappingFilename;
        if (!fs::exists(mappingPath)) {
            cerr << "Warning: Mapping file " << mappingFilename << " not found. Skipping index " << index << endl;
            continue;
        }
        
        vector<MappingRow> mapping = readMappingFile(mappingPath.string());
        if (mapping.empty()) {
            cerr << "Warning: Mapping file " << mappingFilename << " is empty. Skipping index " << index << endl;
            continue;
        }
        
        vector<double> beforeLum, afterLum;
        readLuminanceFile(entry.path().string(), beforeLum, afterLum);
        
        // For this file, store expected pupil sizes for per-person average.
        vector<double> fileLeftBefore, fileRightBefore;
        vector<double> fileLeftAfter, fileRightAfter;
        
        // Process before-window luminance values.
        for (double lum : beforeLum) {
            MappingRow closest = findClosestMapping(mapping, lum);
            globalLeftBefore.push_back(closest.avgLeft);
            globalRightBefore.push_back(closest.avgRight);
            fileLeftBefore.push_back(closest.avgLeft);
            fileRightBefore.push_back(closest.avgRight);
        }
        // Process after-window luminance values.
        for (double lum : afterLum) {
            MappingRow closest = findClosestMapping(mapping, lum);
            globalLeftAfter.push_back(closest.avgLeft);
            globalRightAfter.push_back(closest.avgRight);
            fileLeftAfter.push_back(closest.avgLeft);
            fileRightAfter.push_back(closest.avgRight);
        }
        
        // Compute per-person averages (if there is at least one valid data point).
        auto computeFileAvg = [](const vector<double>& vals) -> double {
            double sum = 0.0;
            int cnt = 0;
            for (double v : vals) {
                if (v != -1) { sum += v; cnt++; }
            }
            return (cnt > 0) ? (sum / cnt) : -1;
        };
        double fileLeftBeforeAvg = computeFileAvg(fileLeftBefore);
        double fileRightBeforeAvg = computeFileAvg(fileRightBefore);
        double fileLeftAfterAvg = computeFileAvg(fileLeftAfter);
        double fileRightAfterAvg = computeFileAvg(fileRightAfter);
        
        if (fileLeftBeforeAvg != -1) perPersonLeftBefore.push_back(fileLeftBeforeAvg);
        if (fileRightBeforeAvg != -1) perPersonRightBefore.push_back(fileRightBeforeAvg);
        if (fileLeftAfterAvg != -1) perPersonLeftAfter.push_back(fileLeftAfterAvg);
        if (fileRightAfterAvg != -1) perPersonRightAfter.push_back(fileRightAfterAvg);
    }
    
    // Aggregate stats over all data points.
    Stats globalLB, globalLA, globalRB, globalRA;
    for (double v : globalLeftBefore)  updateStats(globalLB, v);
    for (double v : globalLeftAfter)   updateStats(globalLA, v);
    for (double v : globalRightBefore) updateStats(globalRB, v);
    for (double v : globalRightAfter)  updateStats(globalRA, v);
    
    // Aggregate stats over per-person averages.
    Stats personLB, personLA, personRB, personRA;
    for (double v : perPersonLeftBefore)  updateStats(personLB, v);
    for (double v : perPersonLeftAfter)   updateStats(personLA, v);
    for (double v : perPersonRightBefore) updateStats(personRB, v);
    for (double v : perPersonRightAfter)  updateStats(personRA, v);
    
    // Print results in the desired format.
    cout << "\nExpected Pupil Size Data\n";
    cout << "Aggregate Pupil Size Statistics (all data points):\n";
    
    cout << "Before Event:\n";
    cout << "  Left Eye\n";
    printStats("Left", globalLB);
    cout << "  Right Eye\n";
    printStats("Right", globalRB);
    
    cout << "\nAfter Event:\n";
    cout << "  Left Eye\n";
    printStats("Left", globalLA);
    cout << "  Right Eye\n";
    printStats("Right", globalRA);
    
    cout << "Per Person Average Pupil Size Statistics (aggregated over indices):\n";
    cout << "Before Event:\n";
    cout << "  Left Eye\n";
    printStats("Left", personLB);
    cout << "  Right Eye\n";
    printStats("Right", personRB);
    
    cout << "\nAfter Event:\n";
    cout << "  Left Eye\n";
    printStats("Left", personLA);
    cout << "  Right Eye\n";
    printStats("Right", personRA);
    
    return 0;
}