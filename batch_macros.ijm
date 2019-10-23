function processFolder(macro_name, input_dir, output_dir) {
	list = getFileList(input_dir);
	for (i = 0; i < list.length; i++) {
		if(!File.isDirectory(input_dir + list[i])) {
			if(macro_name == "processFile") {
				// just an example
				processFile(input_dir, output_dir, list[i]);	
			} else if (macro_name == "sv1") {
				sv1(input_dir, output_dir, list[i]);
			} else if (macro_name == "sv2") {
				sv2(input_dir, output_dir, list[i]);
			}			
		}
	}
}

// example function
function processFile(input_dir, output_dir, file_name) {
	print("processFile function called!");
}

function sv1(input_dir, output_dir, file_name) {
	open(input_dir + file_name);
	
	setMinAndMax(0, 25);
	run("Remove Outliers...", "radius=1 threshold=50 which=Bright");
	run("Despeckle");
	
	setFont("SansSerif",150);
	drawString("+ control\nwatered",270, 810);
	
	setFont("SansSerif",150);
	drawString("+ control\ndesiccated",1800, 3270);
	
	setFont("SansSerif",150);
	drawString("rab18\nwatered",4800, 1000);
	
	setFont("SansSerif",150);
	drawString("rab18\ndesiccated",4900, 3000);
	
	saveAs("Jpeg",  output_dir + File.separator + "processed_" + file_name);
	close();
}

function sv2(input_dir, output_dir, file_name) {
	open(input_dir + file_name);
	
	setMinAndMax(0, 25);
	run("Remove Outliers...", "radius=1 threshold=50 which=Bright");
	run("Despeckle");
	
	run("Line Width...", "line=10");

	makeRectangle(1050, 144, 930, 882); // upper left P6
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("1-Recycling",1220, 300);
	
	makeRectangle(2046, 588, 840, 1026); // upper left P2
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("1-Unrecycled",2118, 768);
	
	makeRectangle(3048, 144, 1296, 948); // upper right P2
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("2-Unrecycled",3400, 310);
	
	makeRectangle(3012, 1266, 1230, 936); // upper right P6
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("2-Recycling",3640, 1420);
	
	makeRectangle(2826, 2292, 1092, 690); // lower left P6
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("3-Recycling",2910, 2950);
	
	makeRectangle(2478, 3084, 1374, 816); // lower left P2
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("3-Unrecycled",3075, 3860);
	
	makeRectangle(4026, 2430, 786, 912); // lower right P2
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("4-Unrecycled",4100, 3300);
	
	makeRectangle(4950, 2856, 900, 1056); // lower right P6
	run("Draw", "slice");
	setFont("SansSerif",100);
	drawString("4-Recycling",5160, 3000);
	
	saveAs("Jpeg",  output_dir + File.separator + "processed_" + file_name);
	close();
}

// hacked a workaround for argument parsing since I can only seem to read in a single arg;
// the calling python script concatenates the 3 arguments together with a "#" delimiter char
// then I split them apart here
args = split(getArgument(),"#");
//print(args.length);
//print(args);
//print(args[0]);
//print(args[1]);
//print(args[2]);

processFolder(args[0], args[1],args[2]);
run("Quit");



