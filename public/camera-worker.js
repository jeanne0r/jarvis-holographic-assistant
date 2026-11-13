// Classic worker: MediaPipe's WASM loader uses importScripts. All assets are local.
self.exports={};
let detector;
self.onmessage=async ({data})=>{
 try{
  if(data.type==='init'){
   importScripts('./vendor/vision/vision_bundle.js');
   const {FilesetResolver,FaceDetector}=self.exports;
   const files=await FilesetResolver.forVisionTasks(new URL('./vendor/vision/wasm',self.location).href);
   detector=await FaceDetector.createFromOptions(files,{baseOptions:{modelAssetPath:new URL('./vendor/vision/face_detector.tflite',self.location).href,delegate:'CPU'},runningMode:'VIDEO',minDetectionConfidence:.65});
   self.postMessage({type:'ready'});
  }else if(data.type==='frame'&&detector){
   const start=performance.now();
   try{
    const faces=detector.detectForVideo(data.bitmap,data.timestamp).detections;
    // Track the most prominent face; no identity, face images or history stored.
    const box=faces.map(f=>f.boundingBox).filter(Boolean).sort((a,b)=>b.width*b.height-a.width*a.height)[0];
    self.postMessage({type:'face',box:box?{x:(box.originX+box.width/2)/data.bitmap.width,y:(box.originY+box.height/2)/data.bitmap.height,width:box.width/data.bitmap.width}:null,ms:performance.now()-start});
   }finally{data.bitmap.close();}
  }
 }catch(error){self.postMessage({type:'error',message:error.message});}
};
